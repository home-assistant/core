_Setup for MacOS sans Docker_

Running homeassistant in Docker container does not allow zcc to function (access to network ports).

The best solution is to run HomeAssistant from the native workspace.

1. Create python environment with "Python: Create Environment" and use "requirements.txt" to populate
2. Install extra packages into Python virtual environment
    .venv/bin/python3 -m pip install zcc-helper 
    .venv/bin/python3 -m pip install -r requirements_test_pre_commit.txt
    .venv/bin/python3 -m pip install -r requirements_test.txt
3. Install extra packagages into system python environment (from outside of VSCode)
    python3 -m pip install pre-commit

Setup VSCode linting etc by adding to the workspace settings:

    "python.terminal.activateEnvInCurrentTerminal": true

