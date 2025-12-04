"""
MCP module-specific creation logic.

Provides additional file generation for MCP modules, including a refresh.py
script that registers the MCP in .vscode/mcp.json.
"""

from __future__ import annotations

from pathlib import Path

from utils.logger_util.logger import Logger

# Template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "data" / "mcps_mod"


class McpModCreator:
    """Handles MCP-specific file generation during module creation."""

    def __init__(self, logger: Logger | None = None):
        self.logger = logger or Logger(name=__class__.__name__)

    def create_mcp_files(self, target: Path, module_name: str) -> None:
        """Create MCP-specific files in the target directory.
        
        Args:
            target: The module directory path
            module_name: The name of the MCP module (e.g., 'vscode_kanbn_mcp')
        """
        self._write_init_py(target, module_name)
        self._write_refresh_py(target, module_name)
        self._write_mcp_server_py(target, module_name)
        self.logger.info(f"Created MCP-specific files in {target}")

    def _write_init_py(self, target: Path, module_name: str) -> None:
        """Generate __init__.py from MCP-specific template, overwriting generic one."""
        init_path = target / "__init__.py"
        
        template_path = TEMPLATE_DIR / "mcp_init_template.txt"
        content = template_path.read_text(encoding="utf-8")
        
        # Replace placeholders
        content = content.format(module_name=module_name)
        
        init_path.write_text(content, encoding="utf-8")
        self.logger.info(f"Created MCP __init__.py at {init_path}")

    def _write_refresh_py(self, target: Path, module_name: str) -> None:
        """Generate refresh.py from template."""
        refresh_path = target / "refresh.py"
        if refresh_path.exists():
            self.logger.debug(f"refresh.py already exists at {refresh_path}, skipping")
            return

        template_path = TEMPLATE_DIR / "mcp_refresh_template.txt"
        content = template_path.read_text(encoding="utf-8")
        
        # Replace placeholders
        content = content.format(module_name=module_name, mcp_key=module_name)
        
        refresh_path.write_text(content, encoding="utf-8")
        self.logger.info(f"Created refresh.py at {refresh_path}")

    def _write_mcp_server_py(self, target: Path, module_name: str) -> None:
        """Generate MCP server file from template."""
        server_path = target / f"{module_name}.py"
        if server_path.exists():
            self.logger.debug(f"{module_name}.py already exists, skipping")
            return

        template_path = TEMPLATE_DIR / "mcp_server_template.txt"
        content = template_path.read_text(encoding="utf-8")
        
        # Replace placeholders
        content = content.format(module_name=module_name)
        
        server_path.write_text(content, encoding="utf-8")
        self.logger.info(f"Created {module_name}.py at {server_path}")

