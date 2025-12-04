from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from managers.config_manager import ConfigManager
from cores.creator_common_core.creator_common_core import (
    RepoCreationOptions,
    TemplateInfo,
    list_templates,
    to_snake_case,
)
from cores.questionary_core.questionary_core import QuestionaryCore
from utils.logger_util.logger import Logger
from cores.exceptions_core.adhd_exceptions import ADHDError
from cores.yaml_reading_core.yaml_reading import YamlReadingCore as yaml_reading
from cores.modules_controller_core.module_types import ModuleTypes

from .module_creator import ModuleCreator, ModuleCreationParams


@dataclass
class ModuleWizardArgs:
    """Pre-filled arguments for module creation wizard."""
    name: Optional[str] = None
    module_type: Optional[str] = None
    template: Optional[str] = None
    create_repo: Optional[bool] = None  # None = ask, True = yes, False = no
    owner: Optional[str] = None
    visibility: Optional[str] = None  # "public" or "private"


def run_module_creation_wizard(
    *,
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: Optional[ModuleWizardArgs] = None,
) -> None:
    """Interactive flow to scaffold a new module.

    - Prompts for module name and type (from main_config.module_types_singular)
    - Optionally creates a GitHub repo similar to project creation flow
    - Generates a minimal module skeleton on disk
    
    Args:
        prompter: QuestionaryCore instance for interactive prompts
        logger: Logger instance
        prefilled: Pre-filled arguments to skip corresponding prompts
    """
    if prefilled is None:
        prefilled = ModuleWizardArgs()

    cm = ConfigManager()
    config = cm.config.module_creator_core
    mod_tmpls = yaml_reading.read_yaml(config.path.module_templates)
    if mod_tmpls is None:
        logger.error("No module templates configuration found.")
        return

    types: list[str] = ModuleTypes().get_all_type_names()
    if not types:
        logger.error("No module types found in ModuleTypes registry.")
        return

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
    except KeyboardInterrupt:
        logger.info("Input cancelled. Exiting.")
        return

    # 2) Pick a module template (optional)
    template_url: Optional[str] = None
    try:
        templates: list[TemplateInfo] = list_templates(mod_tmpls.to_dict())
        
        # Check if prefilled template matches
        if prefilled.template:
            # Try to match by name or URL
            matched = None
            for t in templates:
                if t.name == prefilled.template or t.url == prefilled.template:
                    matched = t
                    break
            if matched:
                template_url = matched.url
                logger.info(f"Using template: {matched.name}")
            elif prefilled.template.startswith(("http://", "https://", "git@")):
                # Assume it's a direct URL
                template_url = prefilled.template
                logger.info(f"Using template URL: {template_url}")
            else:
                logger.warning(f"Template '{prefilled.template}' not found. Proceeding with blank module.")
        elif not templates:
            logger.info("No module templates configured; proceeding with blank module.")
        elif len(templates) == 1:
            # If there's only one template, use it directly without asking.
            only_template = templates[0]
            logger.info(
                f"Single module template detected; using '{only_template.name}' ({only_template.url}) automatically."
            )
            template_url = only_template.url
        else:
            tmpl_lookup = {f"{t.name} — {t.description or t.url}": t for t in templates}
            tmpl_labels = list(tmpl_lookup.keys())
            selected_label = prompter.multiple_choice(
                "Select a module template",
                ["Blank", *tmpl_labels],
                default="Blank",
            )
            if selected_label != "Blank":
                template_url = tmpl_lookup[selected_label].url
    except KeyboardInterrupt:
        logger.info("Template selection cancelled. Exiting.")
        return

    # 3) Ask if a repo should be created (owner/visibility)
    try:
        repo_options = _prompt_repo_creation(prompter, logger, prefilled)
    except KeyboardInterrupt:
        logger.info("Repository creation cancelled. Exiting.")
        return

    # 4) Create the module
    params = ModuleCreationParams(
        module_name=module_name,
        module_type=module_type,
        repo_options=repo_options,
        template_url=template_url,
    )
    creator = ModuleCreator()
    try:
        dest = creator.create(params)
    except ADHDError as exc:  # pragma: no cover - CLI flow
        logger.error(f"❌ Failed to create module: {exc}")
        return

    logger.info(f"✅ Module created at: {dest}")


def _prompt_repo_creation(
    prompter: QuestionaryCore,
    logger: Logger,
    prefilled: ModuleWizardArgs,
) -> Optional[RepoCreationOptions]:
    from cores.github_api_core.api import GithubApi

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
