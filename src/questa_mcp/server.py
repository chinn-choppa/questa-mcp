"""Read-only stdio MCP. В этой версии нет запуска EDA-команд."""

from __future__ import annotations

from mcp.server import MCPServer

from . import __version__
from .diagnostics import parse_diagnostics_text
from .runtime import inspect_tool


def create_server() -> MCPServer:
    """Создать сервер с минимальным проверяемым интерфейсом."""
    server = MCPServer("questa-mcp")

    @server.tool()
    def server_info() -> dict[str, object]:
        """Сообщить о возможностях прототипа без запуска EDA."""
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
        """Найти установленный инструмент, не выполняя его."""
        return inspect_tool("vsim", "QUESTA_MCP_EXECUTABLE")

    @server.tool()
    def parse_diagnostics(text: str, limit: int = 200) -> dict[str, object]:
        """Распознать известные диагностические строки с ограничением размера."""
        return parse_diagnostics_text(text, "vsim", limit)

    return server


def main() -> None:
    """Запустить локальный stdio MCP."""
    create_server().run(transport="stdio")
