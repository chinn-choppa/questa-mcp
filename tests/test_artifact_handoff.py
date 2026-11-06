"""Публичные искусственные файлы и безопасные read-only манифесты."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from questa_mcp.artifact_handoff import (
    MAX_HASH_BYTES, inspect_approved_artifacts, validate_artifact_specs,
)


class ArtifactHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "waves").mkdir()
        (self.root / "waves" / "wave.vcd").write_text(
            "$date synthetic $end\n$timescale 1ns $end\n$enddefinitions $end\n",
            encoding="utf-8",
        )
        (self.root / "waves" / "wave.fst").write_bytes(b"synthetic placeholder, not valid FST")

    def specs(self, entries=None):
        if entries is None:
            entries = [
                {"id": "wave_vcd", "path": "waves/wave.vcd", "format": "vcd",
                 "declared_time_unit": "ns"},
                {"id": "wave_fst", "path": "waves/wave.fst", "format": "fst"}
            ]
        return validate_artifact_specs(entries)

    def test_wavepeek_and_wave_mcp_routes_without_any_external_execution(self):
        report = inspect_approved_artifacts(self.root, self.specs())
        self.assertEqual(report["count"], 2)
        for item in report["items"]:
            self.assertEqual(item["state"], "HASHED")
            self.assertEqual(len(item["sha256"]), 64)
            self.assertIsNone(item["local_path"])
            self.assertFalse(item["paths_disclosed"])
            self.assertFalse(item["format_validated"])
            self.assertIsNone(item["produced_by_run_id"])
            self.assertEqual(item["external_execution"], "NOT_RUN")
            self.assertIn("FORMAT_SUPPORTED_NOT_TESTED", item["routes"]["wavepeek"])
        self.assertEqual(
            report["items"][0]["sha256"],
            hashlib.sha256((self.root / "waves" / "wave.vcd").read_bytes()).hexdigest()
        )
        self.assertEqual(report["items"][0]["declared_time_unit"], "ns")

    def test_explicit_operator_opt_in_can_show_local_paths(self):
        item = inspect_approved_artifacts(self.root, self.specs(), expose_paths=True)["items"][0]
        self.assertEqual(item["local_path"], str(self.root / "waves" / "wave.vcd"))
        self.assertTrue(item["paths_disclosed"])

    def test_wlf_requires_manual_conversion_and_ucdb_is_coverage_only(self):
        (self.root / "x.wlf").write_bytes(b"opaque synthetic WLF placeholder")
        (self.root / "y.ucdb").write_bytes(b"opaque synthetic UCDB placeholder")
        specs = self.specs([
            {"id": "native_wave", "path": "x.wlf", "format": "wlf"},
            {"id": "coverage", "path": "y.ucdb", "format": "ucdb"},
        ])
        items = inspect_approved_artifacts(self.root, specs)["items"]
        self.assertEqual(items[0]["routes"]["wavepeek"], "NOT_SUPPORTED_DIRECTLY")
        self.assertEqual(items[0]["routes"]["conversion"], "VENDOR_WLF2VCD_MANUAL_NOT_RUN")
        self.assertEqual(items[1]["routes"]["coverage"], "VENDOR_UCDB_EXTERNAL_ONLY")
        self.assertEqual(items[1]["routes"]["wave_mcp"], "NOT_APPLICABLE")

    def test_unknown_format_relative_escape_and_duplicates_are_denied(self):
        invalid = [
            [{"id": "x", "path": "../etc/passwd", "format": "vcd"}],
            [{"id": "x", "path": "/etc/passwd", "format": "vcd"}],
            [{"id": "x", "path": "waves\\wave.vcd", "format": "vcd"}],
            [{"id": "x", "path": "C:/wave.vcd", "format": "vcd"}],
            [{"id": "x", "path": "waves/wave.vcd", "format": "bash"}],
            [{"id": "x", "path": "waves/wave.vcd", "format": "fst"}],
            [{"id": "x", "path": "waves/wave.vcd", "format": "vcd",
              "declared_time_unit": "nanoseconds"}],
            [{"id": "x", "path": "x.vcd", "format": "vcd"},
             {"id": "x", "path": "y.vcd", "format": "vcd"}],
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_artifact_specs(value)

    def test_symlink_cannot_escape_allowed_workspace(self):
        outside = self.root.parent / (self.root.name + ".vcd")
        outside.write_bytes(b"synthetic external")
        try:
            link = self.root / "waves" / "outside.vcd"
            link.symlink_to(outside)
            items = inspect_approved_artifacts(
                self.root, self.specs([{"id": "link", "path": "waves/outside.vcd",
                                        "format": "vcd"}])
            )["items"]
            self.assertEqual(items[0]["state"], "MISSING_OR_UNSAFE_PATH")
            self.assertIsNone(items[0]["local_path"])
        except (OSError, NotImplementedError):
            self.skipTest("OS does not permit symlinks")
        finally:
            outside.unlink(missing_ok=True)

    def test_missing_file_is_not_fabricated_as_success(self):
        specs = self.specs([{"id": "missing", "path": "missing.vcd", "format": "vcd"}])
        item = inspect_approved_artifacts(self.root, specs)["items"][0]
        self.assertEqual(item["state"], "MISSING_OR_UNSAFE_PATH")
        self.assertIsNone(item["sha256"])
        self.assertEqual(item["external_execution"], "NOT_RUN")

    def test_large_waveform_is_not_read_or_hashed_by_default(self):
        huge = self.root / "large.vcd"
        with huge.open("wb") as f:
            f.truncate(MAX_HASH_BYTES + 1)
        specs = self.specs([{"id": "huge", "path": "large.vcd", "format": "vcd"}])
        item = inspect_approved_artifacts(self.root, specs)["items"][0]
        self.assertEqual(item["state"], "HASH_SKIPPED_LARGE_FILE")
        self.assertIsNone(item["sha256"])
        self.assertGreater(item["size_bytes"], MAX_HASH_BYTES)

    def test_empty_artifact_list_is_read_only(self):
        report = inspect_approved_artifacts(self.root, validate_artifact_specs(None))
        self.assertEqual(report["items"], [])
        self.assertEqual(report["count"], 0)


if __name__ == "__main__":
    unittest.main()
