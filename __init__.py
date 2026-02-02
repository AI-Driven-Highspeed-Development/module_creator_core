"""module_creator_core - Module creation and scaffolding.

Provides ModuleCreator for creating new ADHD Framework modules.
"""

from __future__ import annotations
from pathlib import Path
import shutil
from functools import lru_cache

TEMPLATE_PATH = "data/module_templates.yaml"


def _get_dest_dir() -> Path:
    """Get the destination directory for template files, creating if needed."""
    dest_dir = Path("./project/data/module_creator_core")
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


def ensure_template() -> Path:
    """Ensure the module template file is copied to the project data directory.
    
    This is called lazily when templates are actually needed, not on import.
    """
    from logger_util import Logger
    logger = Logger(name="ModuleCreatorInit")
    
    dest_dir = _get_dest_dir()
    dest_path = dest_dir / Path(TEMPLATE_PATH).name
    src = Path(__file__).parent / TEMPLATE_PATH
    
    if not src.exists():
        raise FileNotFoundError(f"Bundled template not found: {src}")
    try:
        shutil.copyfile(src, dest_path)
    except Exception as e:
        raise IOError(f"Failed to copy template to {dest_path}: {e}") from e
    
    logger.info(f"Module templates ensured at: {dest_path}")
    return dest_path


@lru_cache(maxsize=1)
def ensure_templates() -> None:
    """Ensure all template files are copied. Called lazily, not on import."""
    ensure_template()


from .module_creator import ModuleCreator, ModuleCreationParams, validate_module_name

__all__ = ["ModuleCreator", "ModuleCreationParams", "validate_module_name", "ensure_templates"]