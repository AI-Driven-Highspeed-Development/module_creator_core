from dataclasses import dataclass
import json
import keyword
from pathlib import Path
import re
from typing import Optional

from config_manager import ConfigManager
from logger_util import Logger
from exceptions_core import ADHDError
from creator_common_core import (
    RepoCreationOptions,
    create_remote_repo,
)
from modules_controller_core import ModuleTypes
from .mcps_mod import McpModCreator


# ============================================================================
# NAME VALIDATION
# Validate module names BEFORE any file operations
# ============================================================================

# Valid module name pattern: lowercase letters, numbers, underscores
# Must start with letter, can't end with underscore
MODULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$|^[a-z]$")


def validate_module_name(name: str) -> None:
    """Validate module name format before any file operations.
    
    Args:
        name: Module name to validate
        
    Raises:
        ADHDError: If name is invalid
    """
    if not name:
        raise ADHDError("Module name cannot be empty")
    
    if keyword.iskeyword(name):
        raise ADHDError(f"Cannot use Python keyword '{name}' as module name")
    
    if len(name) > 50:
        raise ADHDError(f"Module name too long ({len(name)} chars). Maximum is 50 characters.")
    
    if not MODULE_NAME_PATTERN.match(name):
        raise ADHDError(
            f"Invalid module name '{name}'. "
            "Must be snake_case: lowercase letters, numbers, underscores. "
            "Must start with a letter and cannot end with underscore."
        )


# ============================================================================
# TEMPLATE LOADING
# Templates are loaded from data/templates/ directory
# ============================================================================

TEMPLATES_DIR = Path(__file__).parent / "data" / "templates"


def _load_template(name: str) -> str:
    """Load a template file from the templates directory."""
    template_path = TEMPLATES_DIR / name
    if not template_path.exists():
        raise ADHDError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


@dataclass
class ModuleCreationParams:
    module_name: str
    module_type: str  # core/manager/plugin/util/mcp
    description: str = ""  # Optional module description
    repo_options: Optional[RepoCreationOptions] = None
    shows_in_workspace: Optional[bool] = None
    create_instructions: bool = False  # Whether to create .instructions.md file


def _to_class_name(name: str) -> str:
    """Convert snake_case module name to PascalCase class name."""
    return "".join(word.capitalize() for word in name.split("_"))


class ModuleCreator:
    """Scaffold a new module directory structure using embedded templates.
    
    No longer clones external templates - all content is generated from
    embedded Python string constants.
    """

    def __init__(self):
        self.cm = ConfigManager()
        self.config = self.cm.config.module_creator_core
        self.logger = Logger(name=__class__.__name__)

    def create(self, params: ModuleCreationParams) -> Path:
        """Create a new module with embedded templates.
        
        Args:
            params: Module creation parameters
            
        Returns:
            Path to the created module directory.
            
        Raises:
            ADHDError: If module name is invalid
        """
        # CRITICAL: Validate BEFORE any file operations
        validate_module_name(params.module_name)
        
        target = self._prepare_target_path(params)
        
        # Generate all module files from embedded templates
        self._write_pyproject_toml(target, params)
        self._write_init_py(target, params)
        self._write_main_py(target, params)
        self._write_readme(target, params)
        self._write_config_template(target, params)
        
        if params.create_instructions:
            self._write_instructions(target, params)
        
        # Handle module-type-specific files
        if params.module_type == "mcp":
            mcp_creator = McpModCreator(logger=self.logger)
            mcp_creator.create_mcp_files(target, params.module_name)

        # Create remote repo if requested
        if params.repo_options:
            create_remote_repo(
                repo_name=params.module_name,
                local_path=target,
                options=params.repo_options,
                logger=self.logger,
            )
        
        return target

    # ---------------- Path Preparation ----------------
    
    def _prepare_target_path(self, params: ModuleCreationParams) -> Path:
        """Prepare the target directory path for the new module."""
        modules_types = ModuleTypes()
        module_type_info = modules_types.get_module_type(params.module_type)
        directory_name = module_type_info.plural_name
        if not directory_name:
            raise ADHDError(f"Module type '{params.module_type}' not recognized in configuration.")

        modules_root = Path(f"./{directory_name}").resolve()
        modules_root.mkdir(parents=True, exist_ok=True)
        target = (modules_root / params.module_name).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target

    # ---------------- File Generation ----------------

    def _get_template_vars(self, params: ModuleCreationParams) -> dict:
        """Get common template variables for file generation."""
        modules_types = ModuleTypes()
        module_type_info = modules_types.get_module_type(params.module_type)
        return {
            "module_name": params.module_name,
            "module_type": params.module_type,
            "module_type_plural": module_type_info.plural_name,
            "class_name": _to_class_name(params.module_name),
            "description": params.description or f"A {params.module_type} module for ADHD Framework.",
        }

    def _write_pyproject_toml(self, target: Path, params: ModuleCreationParams) -> None:
        """Generate pyproject.toml for new module."""
        vars = self._get_template_vars(params)
        template = _load_template("pyproject.toml.template")
        content = template.format(**vars)
        (target / "pyproject.toml").write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote pyproject.toml at {target / 'pyproject.toml'}")

    def _write_init_py(self, target: Path, params: ModuleCreationParams) -> None:
        """Generate __init__.py for new module."""
        init_py = target / "__init__.py"
        if init_py.exists():
            self.logger.debug(f"__init__.py already exists at {init_py}, skipping")
            return
        vars = self._get_template_vars(params)
        template = _load_template("init.py.template")
        content = template.format(**vars)
        init_py.write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote __init__.py at {init_py}")

    def _write_main_py(self, target: Path, params: ModuleCreationParams) -> None:
        """Generate main module file."""
        # MCP modules have their own main file generation
        if params.module_type == "mcp":
            return
        
        main_py = target / f"{params.module_name}.py"
        if main_py.exists():
            self.logger.debug(f"{params.module_name}.py already exists, skipping")
            return
        vars = self._get_template_vars(params)
        template = _load_template("main_module.py.template")
        content = template.format(**vars)
        main_py.write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote {params.module_name}.py at {main_py}")

    def _write_readme(self, target: Path, params: ModuleCreationParams) -> None:
        """Generate README.md for new module."""
        readme = target / "README.md"
        if readme.exists():
            self.logger.debug(f"README.md already exists at {readme}, skipping")
            return
        vars = self._get_template_vars(params)
        template = _load_template("readme.md.template")
        content = template.format(**vars)
        readme.write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote README.md at {readme}")

    def _write_config_template(self, target: Path, params: ModuleCreationParams) -> None:
        """Generate .config_template for new module."""
        config_template = target / ".config_template"
        if config_template.exists():
            self.logger.debug(f".config_template already exists, skipping")
            return
        vars = self._get_template_vars(params)
        template = _load_template("config.template")
        content = template.format(**vars)
        config_template.write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote .config_template at {config_template}")

    def _write_instructions(self, target: Path, params: ModuleCreationParams) -> None:
        """Generate module instructions file."""
        instructions_file = target / f"{params.module_name}.instructions.md"
        if instructions_file.exists():
            self.logger.debug(f"{params.module_name}.instructions.md already exists, skipping")
            return
        vars = self._get_template_vars(params)
        template = _load_template("instructions.md.template")
        content = template.format(**vars)
        instructions_file.write_text(content, encoding="utf-8")
        self.logger.info(f"Wrote {params.module_name}.instructions.md at {instructions_file}")
