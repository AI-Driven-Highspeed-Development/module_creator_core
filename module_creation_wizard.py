from __future__ import annotations

import re
from typing import Optional

from managers.config_manager import ConfigManager
from cores.creator_common_core.creator_common_core import (
    RepoCreationOptions,
    TemplateInfo,
    list_templates,
)
from cores.questionary_core.questionary_core import QuestionaryCore
from utils.logger_util.logger import Logger
from cores.exceptions_core.adhd_exceptions import ADHDError
from cores.yaml_reading_core.yaml_reading import YamlReadingCore as yaml_reading

from .module_creator import ModuleCreator, ModuleCreationParams


def run_module_creation_wizard(
    *,
    prompter: QuestionaryCore,
    logger: Logger,
) -> None:
    """Interactive flow to scaffold a new module.

    - Prompts for module name and type (from main_config.module_types_singular)
    - Optionally creates a GitHub repo similar to project creation flow
    - Generates a minimal module skeleton on disk
    """

    cm = ConfigManager()
    config = cm.config.module_creator_core
    mod_tmpls = yaml_reading.read_yaml(config.path.module_templates)
    if mod_tmpls is None:
        logger.error("No module templates configuration found.")
        return
    types: list[str] = list(config.module_types_singular)
    if not types:
        logger.error("No module types configured in main_config.module_types_singular")
        return

    # 1) Ask for module name and type
    try:
        raw_name = prompter.autocomplete_input(
            "Module name",
            choices=[],
            default="my_module",
        )
        module_name = _to_snake_case(raw_name)
        if module_name != raw_name:
            logger.info(f"Module name normalized to '{module_name}'")

        module_type = prompter.multiple_choice(
            "Module type",
            types,
            default=types[0],
        )
    except KeyboardInterrupt:
        logger.info("Input cancelled. Exiting.")
        return

    # 2) Pick a module template (optional)
    template_url: Optional[str] = None
    try:
        templates: list[TemplateInfo] = list_templates(mod_tmpls.to_dict())
        if not templates:
            logger.info("No module templates configured; proceeding with blank module.")
        elif len(templates) == 1:
            # If there's only one template, use it directly without asking.
            only_template = templates[0]
            logger.info(
                "Single module template detected; using '%s' (%s) automatically.",
                only_template.name,
                only_template.url,
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
        repo_options = _prompt_repo_creation(prompter, logger)
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


def _prompt_repo_creation(prompter: QuestionaryCore, logger: Logger) -> Optional[RepoCreationOptions]:
    from cores.github_api_core.api import GithubApi

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

    # repo_url will be derived consistently by the creator at write time,
    # so we don't need to construct it here beyond passing owner/visibility.
    return RepoCreationOptions(owner=owner, visibility=visibility)


def _to_snake_case(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    result = cleaned.lower()
    return result or "module"


__all__ = ["run_module_creation_wizard"]
