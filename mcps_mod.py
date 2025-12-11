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


def _derive_module_base(module_name: str) -> str:
    """Derive the base name from a module name (strip _mcp suffix if present).
    
    Examples:
        vscode_kanbn_mcp -> kanbn
        unity_mcp -> unity
        adhd_mcp -> adhd
    """
    if module_name.endswith("_mcp"):
        base = module_name[:-4]  # Remove _mcp suffix
        # If base has a prefix like 'vscode_', strip it for controller name
        parts = base.split("_")
        if len(parts) > 1:
            return parts[-1]  # Use last part (e.g., 'kanbn' from 'vscode_kanbn')
        return base
    return module_name


def _to_class_name(name: str) -> str:
    """Convert snake_case to PascalCase for class names."""
    return "".join(word.capitalize() for word in name.split("_"))


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
        self._write_cli_py(target, module_name)
        self.logger.info(f"Created MCP-specific files in {target}")

    def _get_placeholders(self, module_name: str) -> dict[str, str]:
        """Build placeholder dict for template substitution."""
        module_base = _derive_module_base(module_name)
        return {
            "module_name": module_name,
            "mcp_key": module_name,
            "module_base": module_base,
            "module_class": _to_class_name(module_base),
            "short_name": module_base[:4],  # First 4 chars as short name
            "module_description": f"{module_name} CLI commands",
        }

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
        placeholders = self._get_placeholders(module_name)
        content = content.format(**placeholders)
        
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

    def _write_cli_py(self, target: Path, module_name: str) -> None:
        """Generate CLI file from template."""
        module_base = _derive_module_base(module_name)
        cli_path = target / f"{module_base}_cli.py"
        if cli_path.exists():
            self.logger.debug(f"{module_base}_cli.py already exists, skipping")
            return

        template_path = TEMPLATE_DIR / "mcp_cli_template.txt"
        if not template_path.exists():
            self.logger.debug("mcp_cli_template.txt not found, skipping CLI generation")
            return
            
        content = template_path.read_text(encoding="utf-8")
        
        # Replace placeholders
        placeholders = self._get_placeholders(module_name)
        content = content.format(**placeholders)
        
        cli_path.write_text(content, encoding="utf-8")
        self.logger.info(f"Created {module_base}_cli.py at {cli_path}")

