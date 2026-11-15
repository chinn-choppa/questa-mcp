"""Локальный read-only MCP поверх stdio; исполнение EDA пока запрещено."""

from __future__ import annotations

from typing import Literal

from mcp.server import MCPServer

from . import __version__
from .diagnostics import parse_diagnostics_text
from .runtime import inspect_tool


def create_server() -> MCPServer:
    """Создать MCP-сервер с ограниченными и типизированными инструментами."""
    server = MCPServer("questa-mcp")

    @server.tool()
    def server_info() -> dict[str, object]:
        """Показать возможности, не выполняя Questa/ModelSim."""
        return {
            "server": "questa-mcp",
            "version": __version__,
            "vendor_tool": "vsim",
            "stage": "bootstrap",
            "operations": ["server_info", "tool_status", "parse_diagnostics"],
            "eda_execution_supported": False,
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

    return server


def main() -> None:
    """Запустить локальный MCP по stdio."""
    create_server().run(transport="stdio")
