from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Optional
import yaml

from managers.config_manager import ConfigManager
from utils.logger_util.logger import Logger
from cores.exceptions_core.adhd_exceptions import ADHDError
from cores.creator_common_core.creator_common_core import (
    RepoCreationOptions,
    clone_template,
    create_remote_repo,
)
from cores.github_api_core.api import GithubApi
from cores.modules_controller_core.module_types import ModuleTypes

@dataclass
class ModuleCreationParams:
    module_name: str
    module_type: str  # core/manager/plugin/util/mcp
    repo_options: Optional[RepoCreationOptions] = None
    template_url: Optional[str] = None
    shows_in_workspace: Optional[bool] = None


class ModuleCreator:
    """Scaffold a new module directory structure and optional remote repo."""

    def __init__(self):
        self.cm = ConfigManager()
        self.config = self.cm.config.module_creator_core
        self.logger = Logger(name=__class__.__name__)

    def create(self, params: ModuleCreationParams) -> Path:
        target = self._prepare_target_path(params)
        api = GithubApi()

        # If a template is provided, clone it first
        if params.template_url:
            clone_template(api, params.template_url, target)

        self._write_init_yaml(target, params)
        self._write_placeholder_files(target, params)

        if params.repo_options:
            create_remote_repo(
                api=api,
                repo_name=params.module_name,
                local_path=target,
                options=params.repo_options,
                logger=self.logger,
            )
        return target


    # ---------------- Internal helpers ----------------
    def _prepare_target_path(self, params: ModuleCreationParams) -> Path:
        # Determine plural directory name from config mapping with safe fallbacks
        modules_types = ModuleTypes()
        directory_name = modules_types.get_module_type(params.module_type).plural_name
        if not directory_name:
            raise ADHDError(f"Module type '{params.module_type}' not recognized in configuration.")

        modules_root = Path(f"./{directory_name}").resolve()
        modules_root.mkdir(parents=True, exist_ok=True)
        target = (modules_root / params.module_name).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _write_init_yaml(self, target: Path, params: ModuleCreationParams) -> None:
        init_path = target / "init.yaml"

        relative_folder = target.relative_to(Path.cwd())
        repo_url: Optional[str] = None
        if params.repo_options is not None:
            owner = params.repo_options.owner
            if owner:
                try:
                    repo_url = GithubApi.build_repo_url(owner, params.module_name)
                    params.repo_options.repo_url = repo_url
                except ValueError:
                    repo_url = None

        data = {
            "version": "0.0.1",
            "folder_path": str(relative_folder).replace("\\", "/"),  # Legacy property, need drop after bootstrapping
            "type": params.module_type,
            "requirements": [],  # populated manually by user if needed
        }

        # Check if we need to override the default visibility
        module_types = ModuleTypes()
        mt = module_types.get_module_type(params.module_type)
        default_visibility = mt.shows_in_workspace
        
        if params.shows_in_workspace is not None and params.shows_in_workspace != default_visibility:
             data["shows_in_workspace"] = params.shows_in_workspace

        if repo_url:
            data["repo_url"] = repo_url
        
        with open(init_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        self.logger.info(f"Wrote init.yaml at {init_path}")

    def _write_placeholder_files(self, target: Path, params: ModuleCreationParams) -> None:
        # Basic Python package structure
        init_py = target / "__init__.py"
        if not init_py.exists():
            init_py.write_text(f'"""{params.module_name} {params.module_type} module."""\n', encoding="utf-8")
        readme = target / "README.md"
        if not readme.exists():
            readme.write_text(f"# {params.module_name}\n\nType: {params.module_type}\n", encoding="utf-8")
        self.logger.info(f"Created module files in {target}")
