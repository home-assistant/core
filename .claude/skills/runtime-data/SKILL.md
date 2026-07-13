---
name: runtime-data
description: Migrate integration to use runtime_data. Use when the user says "Migrate integration <integration_name> to use runtime_data".
---

# Prepare
- switch to dev branch and update it using "git checkout dev && git pull"

# Migrate integration to use runtime_data
- if coordinator module exists, ensure typed config entry is declared in coordinator module and update coordinator to use typed config entry
- if async_get_options_flow in config_flow module references ConfigEntry, ensure it is updated to use typed config entry instead
- if quality_scale file exists, mark runtime_data as done
- ensure ruff checks and ruff format still works after the move
- ensure `mypy homeassistant/components/<integration_name>` still passes
- ensure `pytest tests/components/<integration_name>` still passes
- if needed, update import of constants in tests from const.py to avoid unused imports in __init__.py

# Finalize Changes
- create a new branch prefixed with "{current_user}/"
- commit the changes to the new branch with a clear message
- create PR using raise-pull-request agent