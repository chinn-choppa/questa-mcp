"""Локальный MCP со строго разрешённым экспериментальным исполнителем DO."""

from __future__ import annotations

from typing import Literal

from .approved import (
    list_approved_artifacts as artifacts_list,
    list_run_artifacts as run_artifacts_list,
    list_approved_projects as approved_list,
    run_approved_project as approved_run,
)

from mcp.server import MCPServer

from . import __version__
from .diagnostics import parse_diagnostics_text
from .runtime import inspect_tool
from .phase_runner import run_approved_regression as approved_regression
from .verification import assess_run, assess_regression as summarize_regression


def create_server() -> MCPServer:
    """Создать MCP-сервер с ограниченными и типизированными инструментами."""
    server = MCPServer("questa-mcp")
    running_projects: set[str] = set()

    @server.tool()
    def server_info() -> dict[str, object]:
        """Показать возможности, не выполняя Questa/ModelSim."""
        enabled = approved_list()["state"] == "CONFIGURED"
        return {
            "server": "questa-mcp",
            "version": __version__,
            "vendor_tool": "vsim",
            "stage": "bootstrap",
            "operations": ["server_info", "tool_status", "parse_diagnostics",
                           "list_approved_projects", "run_approved_project",
                           "assess_verification_run", "assess_regression",
                           "list_approved_artifacts", "list_run_artifacts",
                           "run_approved_regression"],
            "eda_execution_supported": enabled,
        }

    @server.tool()
    def tool_status() -> dict[str, object]:
        """Обнаружить vsim без запуска и раскрытия полного пути."""
        return inspect_tool("vsim", "QUESTA_MCP_EXECUTABLE")

    @server.tool()
    def parse_diagnostics(
        text: str, tool: Literal["vsim", "vlog", "vcom"] = "vsim", limit: int = 200
    ) -> dict[str, object]:
        """Разобрать текстовый журнал; без подтверждения PASS."""
        return parse_diagnostics_text(text, tool, limit)

    @server.tool()
    def list_approved_projects() -> dict[str, object]:
        """Перечислить разрешённые IDs без путей и DO-содержимого."""
        return approved_list()

    @server.tool()
    def list_approved_artifacts(project_id: str) -> dict[str, object]:
        """Выдать только metadata разрешённых VCD/FST/WLF/UCDB без загрузок."""
        return artifacts_list(project_id)

    @server.tool()
    def list_run_artifacts(project_id: str, run_id: str) -> dict[str, object]:
        """Описание файлов конкретного каталога запуска, без произвольных путей."""
        return run_artifacts_list(project_id, run_id)

    @server.tool()
    async def run_approved_project(project_id: str) -> dict[str, object]:
        """Запустить только заранее разрешённый DO-профиль, без Tcl аргументов."""
        if project_id in running_projects:
            return {"status": "BUSY", "test_verdict": "UNKNOWN", "eda_executed": False}
        running_projects.add(project_id)
        try:
            return await approved_run(project_id)
        finally:
            running_projects.discard(project_id)

    @server.tool()
    async def run_approved_regression(project_id: str) -> dict[str, object]:
        """Запустить фиксированные три фазы и seed из локального профиля."""
        if project_id in running_projects:
            return {"status": "BUSY", "regression_verdict": "UNKNOWN", "runs": []}
        running_projects.add(project_id)
        try:
            return await approved_regression(project_id)
        finally:
            running_projects.discard(project_id)

    @server.tool()
    def assess_verification_run(record: dict[str, object]) -> dict[str, object]:
        """Разобрать данные о фазах; клиентские свидетельства никогда не дают PASS."""
        return assess_run(record)

    @server.tool()
    def assess_regression(runs: list[dict[str, object]]) -> dict[str, object]:
        """Агрегировать фазовые результаты без повышения недоверенного PASS."""
        return summarize_regression(runs)

    return server


def main() -> None:
    """Запустить локальный MCP по stdio."""
    create_server().run(transport="stdio")
