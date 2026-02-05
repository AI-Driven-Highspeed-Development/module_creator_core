from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from creator_common_core import (
    RepoCreationOptions,
    to_snake_case,
    QuestionaryCore,
)
from logger_util import Logger
from exceptions_core import ADHDError
from modules_controller_core import LAYER_SUBFOLDERS

from .module_creator import (
    ModuleCreator, 
    ModuleCreationParams,
)


@dataclass
class ModuleWizardArgs:
    """Pre-filled arguments for module creation wizard."""
    name: Optional[str] = None
    layer: Optional[str] = None  # foundation, runtime, dev
    is_mcp: Optional[bool] = None  # Whether to create an MCP module
    description: Optional[str] = None  # Optional module description
    create_instructions: Optional[bool] = None  # Whether to create .instructions.md
    # DEPRECATED_P3: template no longer used - embedded templates only
    create_repo: Optional[bool] = None  # None = ask, True = yes, False = no
    owner: Optional[str] = None
    visibility: Optional[str] = None  # "public" or "private"


# Layer descriptions for wizard
LAYER_DESCRIPTIONS = {
    "foundation": "Bootstrap modules - core infrastructure, no ADHD deps",
    "runtime": "Production modules - most modules go here (default)",
    "dev": "Development tools - testing, debugging, build utilities",
}


def run_module_creation_wizard(
    *,
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: Optional[ModuleWizardArgs] = None,
) -> None:
    """Interactive flow to scaffold a new module using embedded templates.

    - Prompts for module name, layer, and MCP flag
    - Optionally creates a GitHub repo
    - Generates module files from embedded templates
    
    Args:
        prompter: QuestionaryCore instance for interactive prompts
        logger: Logger instance
        prefilled: Pre-filled arguments to skip corresponding prompts
    """
    if prefilled is None:
        prefilled = ModuleWizardArgs()

    # 1) Ask for module name, layer, and MCP flag
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

        # Layer selection
        if prefilled.layer:
            if prefilled.layer not in LAYER_SUBFOLDERS:
                logger.error(f"Invalid layer '{prefilled.layer}'. Valid layers: {', '.join(LAYER_SUBFOLDERS)}")
                return
            layer = prefilled.layer
        else:
            # Build layer choices with descriptions
            layer_choices = [f"{layer} - {LAYER_DESCRIPTIONS.get(layer, '')}" for layer in LAYER_SUBFOLDERS]
            layer_choice = prompter.multiple_choice(
                "Module layer (determines when module loads)",
                layer_choices,
                default=layer_choices[1],  # runtime is default
            )
            # Extract layer from choice ("runtime - Production modules..." -> "runtime")
            layer = layer_choice.split(" - ")[0]

        # MCP flag
        if prefilled.is_mcp is not None:
            is_mcp = prefilled.is_mcp
        else:
            mcp_choice = prompter.multiple_choice(
                "Is this an MCP (Model Context Protocol) module for AI agents?",
                ["No", "Yes"],
                default="No",
            )
            is_mcp = mcp_choice == "Yes"
        
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
    params = ModuleCreationParams(
        module_name=module_name,
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
