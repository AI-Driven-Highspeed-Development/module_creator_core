# Module Creator Core

Compact scaffolder for ADHD Framework modules with optional GitHub repository bootstrap and template cloning.

## Overview
- Normalizes module names/types via the interactive wizard powered by Questionary Core
- Clones optional templates and removes their `.git` metadata before writing new files
- Writes `init.yaml`, README stub, and `__init__.py` tailored to the selected module type
- Integrates with Github API Core + Creator Common Core to provision remote repos and push the first commit

## Features
- **Interactive wizard** – guides users through naming, module type selection, template choice, and repo ownership
- **Programmatic API** – `ModuleCreator` + `ModuleParams` allow scripted scaffolding from automation or tests
- **Template hydration** – clones template repositories listed in `data/module_creator_core/module_templates.yaml`
- **Repo automation** – automatically computes `repo_url`, creates the remote, and pushes the initial commit when requested

## Quickstart

Programmatic creation:

```python
from cores.module_creator_core.module_creator import ModuleCreator, ModuleParams
from cores.creator_common_core.creator_common_core import RepoCreationOptions

params = ModuleParams(
	module_name="github_sync",
	module_type="core",
	repo_options=RepoCreationOptions(owner="my-org", visibility="private"),
	template_url="https://github.com/org/module-template",
)

creator = ModuleCreator()
module_path = creator.create(params)
print(f"Module scaffolded at {module_path}")
```

Interactive wizard:

```python
from cores.module_creator_core.module_creation_wizard import run_module_creation_wizard
from cores.questionary_core.questionary_core import QuestionaryCore
from utils.logger_util.logger import Logger

run_module_creation_wizard(
	prompter=QuestionaryCore(),
	logger=Logger("ModuleWizard"),
)
```

## API

```python
@dataclass
class ModuleParams:
	module_name: str
	module_type: str  # core | manager | plugin | util | mcp
	repo_options: RepoCreationOptions | None = None
	template_url: str | None = None

class ModuleCreator:
	def __init__(self) -> None: ...
	def create(self, params: ModuleParams) -> pathlib.Path: ...

def run_module_creation_wizard(*, prompter: QuestionaryCore, logger: Logger) -> None: ...
```

## Notes
- The wizard reads module types and template locations from `main_config`; keep that file in sync with project data.
- `ModuleCreator` always writes `init.yaml` with `folder_path`, version `0.0.1`, requirements stub, and `repo_url` when available.
- Template cloning removes `.git` folders so the new repo starts with a clean history.

## Requirements & prerequisites
- GitHub CLI (`gh`) and git (for cloning + pushes)
- Python dependency: `pyyaml`
- ConfigManager must be initialized so module type mappings and data paths are available

## Troubleshooting
- **“Module type '...' not recognized”** – ensure the type exists under `main_config.module_types_singular`.
- **Template selection shows only “Blank”** – verify `project/data/module_creator_core/module_templates.yaml` exists and contains entries.
- **Remote repo creation failed** – confirm GitHub CLI authentication and that you have rights to the selected owner.
- **`repo_url` missing in init.yaml** – repository owner must be provided; otherwise the URL is omitted by design.

## Module structure

```
cores/module_creator_core/
├─ __init__.py                    # copies bundled templates into project/data
├─ module_creator.py              # ModuleCreator + params dataclass
├─ module_creation_wizard.py      # interactive CLI workflow
├─ data/
│  └─ module_templates.yaml       # bundled template catalog copied into project/data
├─ init.yaml                      # module metadata
└─ README.md                      # this file
```

## See also
- Creator Common Core – shared clone/repo helpers
- GitHub API Core – low-level gh wrapper used for cloning/pushing
- Questionary Core – provides the prompts powering the wizard
- Project Creator Core – complementary scaffolder for full projects