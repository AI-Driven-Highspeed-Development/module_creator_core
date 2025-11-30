from __future__ import annotations
from pathlib import Path
import shutil
import os
import sys

# Add path handling to work from the new nested directory structure
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.getcwd()  # Use current working directory as project root
sys.path.insert(0, project_root)

TEMPLATE_PATH = "data/module_templates.yaml"

from utils.logger_util.logger import Logger
logger = Logger(name="ModuleCreatorInit")

dest_dir = Path("./project/data/module_creator_core")
if dest_dir.exists():
    shutil.rmtree(dest_dir)
dest_dir.mkdir(parents=True, exist_ok=True)

dest_path = dest_dir / Path(TEMPLATE_PATH).name
src = Path(__file__).parent / TEMPLATE_PATH
if not src.exists():
    raise FileNotFoundError(f"Bundled template not found: {src}")
try:
    shutil.copyfile(src, dest_path)
except Exception as e:
    raise IOError(f"Failed to copy template to {dest_path}: {e}") from e

logger.info(f"Module templates ensured at: {dest_path}")