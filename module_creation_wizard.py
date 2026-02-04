from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from creator_common_core import (
    RepoCreationOptions,
    to_snake_case,
)
from questionary_core import QuestionaryCore
from logger_util import Logger
from exceptions_core import ADHDError
from modules_controller_core import ModuleLayer

from .module_creator import (
    ModuleCreator, 
    ModuleCreationParams,
    FOLDER_TO_SINGULAR,
    SINGULAR_TO_FOLDER,
)


@dataclass
class ModuleWizardArgs:
    """Pre-filled arguments for module creation wizard."""
    name: Optional[str] = None
    module_type: Optional[str] = None  # Singular: manager, util, plugin, mcp, core
    description: Optional[str] = None  # Optional module description
    create_instructions: Optional[bool] = None  # Whether to create .instructions.md
    # DEPRECATED_P3: template no longer used - embedded templates only
    create_repo: Optional[bool] = None  # None = ask, True = yes, False = no
    owner: Optional[str] = None
    visibility: Optional[str] = None  # "public" or "private"


# Available module types (singular form for UI)
MODULE_TYPES = list(FOLDER_TO_SINGULAR.values())

# Default layer mapping by folder
FOLDER_LAYER_DEFAULTS = {
    "cores": "foundation",
    "utils": "foundation",
    "managers": "runtime",
    "plugins": "runtime",
    "mcps": "dev",
}


def _infer_layer_from_folder(folder: str) -> str:
    """Infer default layer from folder name."""
    return FOLDER_LAYER_DEFAULTS.get(folder, "runtime")


def run_module_creation_wizard(
    *,
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: Optional[ModuleWizardArgs] = None,
) -> None:
    """Interactive flow to scaffold a new module using embedded templates.

    - Prompts for module name and type
    - Optionally creates a GitHub repo
    - Generates module files from embedded templates
    
    Args:
        prompter: QuestionaryCore instance for interactive prompts
        logger: Logger instance
        prefilled: Pre-filled arguments to skip corresponding prompts
    """
    if prefilled is None:
        prefilled = ModuleWizardArgs()

    # Use defined module types (singular form)
    types = MODULE_TYPES.copy()

    # Reorder types: move "core" to the end (cores are advanced/internal)
    if "core" in types:
        types = [t for t in types if t != "core"] + ["core"]

    # 1) Ask for module name and type
    try:
        # Module name
        if prefilled.name:
            module_name = to_snake_case(prefilled.name)
            if module_name != prefilled.name:
                logger.info(f"Module name normalized to '{module_name}'")
        else:
            raw_name = prompter.autocomplete_input(
                "Module name",
                choices=[],
                default="my_module",
            )
            module_name = to_snake_case(raw_name)
            if module_name != raw_name:
                logger.info(f"Module name normalized to '{module_name}'")

        # Module type
        if prefilled.module_type:
            if prefilled.module_type not in types:
                logger.error(f"Invalid module type '{prefilled.module_type}'. Valid types: {', '.join(types)}")
                return
            module_type = prefilled.module_type
        else:
            module_type = prompter.multiple_choice(
                "Module type",
                types,
                default=types[0],
            )

        # Warn user if they select "core" type
        if module_type == "core":
            logger.warning(
                "⚠️  Cores are internal framework components. "
                "Only create a core if you're extending the ADHD framework itself."
            )
            confirm = prompter.multiple_choice(
                "Are you sure you want to create a core module?",
                ["Yes, I understand", "No, go back"],
                default="No, go back",
            )
            if confirm != "Yes, I understand":
                logger.info("Core creation cancelled. Please restart and select a different module type.")
                return
        
        # Optional description
        description = prefilled.description or ""
        
        # Ask about instructions file
        create_instructions = prefilled.create_instructions
        if create_instructions is None:
            create_instr_choice = prompter.multiple_choice(
                "Create instructions file (.instructions.md) for AI agents?",
                ["No", "Yes"],
                default="No",
            )
            create_instructions = create_instr_choice == "Yes"

    except KeyboardInterrupt:
        logger.info("Input cancelled. Exiting.")
        return

    # 2) Ask if a repo should be created (owner/visibility)
    try:
        repo_options = _prompt_repo_creation(prompter, logger, prefilled)
    except KeyboardInterrupt:
        logger.info("Repository creation cancelled. Exiting.")
        return

    # 3) Create the module using embedded templates
    # Convert singular type to folder name (e.g., 'manager' -> 'managers')
    folder = SINGULAR_TO_FOLDER.get(module_type, module_type)
    is_mcp = module_type == "mcp"
    
    # Infer default layer from folder
    layer = _infer_layer_from_folder(folder)
    
    params = ModuleCreationParams(
        module_name=module_name,
        folder=folder,
        layer=layer,
        is_mcp=is_mcp,
        description=description,
        repo_options=repo_options,
        create_instructions=create_instructions,
    )
    creator = ModuleCreator()
    try:
        dest = creator.create(params)
    except ADHDError as exc:  # pragma: no cover - CLI flow
        logger.error(f"❌ Failed to create module: {exc}")
        return

    logger.info(f"✅ Module created at: {dest}")
    logger.info("Next steps:")
    logger.info("  uv sync  # to install the new module")
    logger.info("  # Then import from your code: from {module_name} import ...")


def _prompt_repo_creation(
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: ModuleWizardArgs,
) -> Optional[RepoCreationOptions]:
    from github_api_core import GithubApi

    # Check if repo creation is pre-determined
    if prefilled.create_repo is False:
        return None
    
    if prefilled.create_repo is None:
        try:
            create_choice = prompter.multiple_choice(
                "Create a GitHub repository for this module?",
                ["Yes", "No"],
                default="Yes",
            )
        except KeyboardInterrupt:
            logger.info("Repository creation choice cancelled. Exiting.")
            raise

        if create_choice != "Yes":
            return None

    try:
        api = GithubApi()
        user_login = api.get_authenticated_user_login()
    except ADHDError as exc:
        logger.error(f"Failed to initialize GitHub CLI: {exc}")
        return None

    try:
        orgs = api.get_user_orgs()
    except ADHDError as exc:
        logger.error(f"Failed to fetch organizations: {exc}")
        orgs = []

    owner_lookup: dict[str, str] = {}
    if user_login:
        owner_lookup[f"{user_login} (personal)"] = user_login

    for org in orgs:
        login = org.get("login")
        if login and login not in owner_lookup.values():
            owner_lookup[f"{login} (org)"] = login

    if not owner_lookup:
        logger.error("No eligible GitHub owners found; skipping repository creation.")
        return None

    # Owner selection
    if prefilled.owner:
        # Validate the prefilled owner
        if prefilled.owner in owner_lookup.values():
            owner = prefilled.owner
        else:
            logger.error(f"Owner '{prefilled.owner}' not found. Available: {', '.join(owner_lookup.values())}")
            return None
    else:
        owner_labels = list(owner_lookup.keys())
        try:
            owner_label = prompter.multiple_choice(
                "Select repository owner",
                owner_labels,
                default=owner_labels[0],
            )
        except KeyboardInterrupt:
            logger.info("Repository owner selection cancelled. Exiting.")
            raise
        owner = owner_lookup[owner_label]

    # Visibility selection
    if prefilled.visibility:
        if prefilled.visibility not in ["public", "private"]:
            logger.error(f"Invalid visibility '{prefilled.visibility}'. Must be 'public' or 'private'.")
            return None
        visibility = prefilled.visibility
    else:
        try:
            visibility_choice = prompter.multiple_choice(
                "Repository visibility",
                ["Public", "Private"],
                default="Private",
            )
        except KeyboardInterrupt:
            logger.info("Repository visibility selection cancelled. Exiting.")
            raise
        visibility = "private" if visibility_choice == "Private" else "public"

    return RepoCreationOptions(owner=owner, visibility=visibility)


__all__ = ["run_module_creation_wizard", "ModuleWizardArgs"]
