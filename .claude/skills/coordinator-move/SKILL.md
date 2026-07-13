---
name: coordinator-move
description: Move integration DataUpdateCoordinator to separate module. Use when the user says "move the DataUpdateCoordinator for integration <integration_name>".
---

# Prepare to Move DataUpdateCoordinator
- switch to dev branch and update it using "git checkout dev && git pull"

# Move DataUpdateCoordinator
- create a new coordinator module in the integration directory
- move DataUpdateCoordinator to new subclass and related code to the new file
- ensure that coordinator config_entry is typed at the class level
- if typed config entry exists in __init__.py, ensure it is declared in coordinator module, avoiding re-export
- if class for runtime_data exists in __init__.py, ensure it is declared in coordinator module, avoiding re-export
- if typed config entry doesn't exist, do not create it
- update the __init__.py file to import the coordinator from the new file
- update any references to the coordinator in the integration code to use the new import path
- ensure ruff checks and ruff format still works after the move
- ensure mypy still passes after the move
- ensure pytest still passes after the move

# Finalize Changes
- create a new branch prefixed with "{current_user}/"
- commit the changes to a new branch with a clear message indicating the coordinator has been moved
- do not attempt to amend previous commits, as this can cause issues with the commit history and make it difficult for others to review the changes. Instead, create a new commit that includes all the necessary changes and improvements.
- push the changes to the remote repository
- create draft PR using "pr-template.txt" template without modifications