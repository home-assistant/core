# GitHub Copilot & Claude Code Instructions

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Git Commit Guidelines

- **Do NOT amend, squash, or rebase commits that have already been pushed to the PR branch after the PR is opened** - Reviewers need to follow the commit history, as well as see what changed since their last review

## Pull Requests

- When opening a pull request, use the repository's PR template (`.github/PULL_REQUEST_TEMPLATE.md`). NEVER REMOVE ANYTHING from the template.
- Do not remove checkboxes that are not checked — leave all unchecked checkboxes in place so reviewers can see which options were not selected.

## Development Commands

- Run "python3" in current virtual environment to ensure the correct Python version is used for testing.
- When entering a new environment or worktree, run `script/setup` to set up the virtual environment with all development dependencies (pylint, pre-commit hooks, etc.). This is required before committing. If uv reports that no download was found for the required Python version, the environment is running an outdated version of uv; upgrade it with `curl -LsSf https://astral.sh/uv/install.sh | sh` and run `script/setup` again.
- .vscode/tasks.json contains useful commands used for development.
- After finishing a code session, run `uv run prek run --all-files` to check for linting and formatting issues.

## Python Syntax Notes

- Home Assistant officially supports Python 3.14 as its minimum version. Do not flag syntax or features that require Python 3.14 as issues, and do not suggest workarounds for older Python versions.
- Python 3.14 explicitly allows `except TypeA, TypeB:` without parentheses. Never flag this as an issue.
- Python 3.14 evaluates annotations lazily (PEP 649). Forward references in annotations do not need to be quoted — annotations can reference names defined later in the module without quoting them or using `from __future__ import annotations`. Do not flag unquoted forward references in annotations as issues.

## Testing

- Use `uv run pytest` to run tests
- After modifying `strings.json` for an integration, regenerate the English translation file before running tests: `python3 -m script.translations develop --integration <integration_name>`. Tests load translations from the generated `translations/en.json`, not directly from `strings.json`.
- When writing or modifying tests, ensure all test function parameters have type annotations.
- Prefer concrete types (for example, `HomeAssistant`, `MockConfigEntry`, etc.) over `Any`.
- Prefer `@pytest.mark.usefixtures` over arguments, if the argument is not going to be used.
- Avoid using conditions/branching in tests. Instead, either split tests or adjust the test parametrization to cover all cases without branching.
- If multiple tests share most of their code, use `pytest.mark.parametrize` to merge them into a single parameterized test instead of duplicating the body. Use `pytest.param` with an `id` parameter to name the test cases clearly.
- We use Syrupy for snapshot testing. Leverage `.ambr` snapshots instead of repetitive and exhaustive generation of test data within Python code itself.
- Hardcoded `entity_id`s in tests are fine. If the same one is repeated, use a constant.

## Good practices

- Integrations with Platinum or Gold level in the Integration Quality Scale reflect a high standard of code quality and maintainability. When looking for examples of something, these are good places to start. The level is indicated in the manifest.json of the integration.
- When reviewing entity actions, do not suggest extra defensive checks for input fields that are already validated by Home Assistant's service/action schemas and entity selection filters. Suggest additional guards only when data bypasses those validators or is transformed into a less-safe form.
- When validation guarantees a dict key exists, prefer direct key access (`data["key"]`) instead of `.get("key")` so contract violations are surfaced instead of silently masked.
- Keep comments concise. Prefer one short line stating the non-obvious constraint, or no comment at all.
- Do not add comments that just restate the code on the following line(s) (e.g. `# Check if initialized` above `if self.initialized:`). Comments should only explain why (non-obvious constraints, surprising behavior, or workarounds), never what. Never add comments that justify a change by referencing what the code looked like before. Comments in tests that explain why a function call or assertion is made are ok.
- Do not add section or divider comments (e.g. `# --- XYZ Triggers ---`) inside or outside of functions, since those can easily become stale and be misleading.
- When catching exceptions, try-clauses should be as small as possible, i.e. avoid wrapping large blocks of code in a try-clause, and avoid catching exceptions from functions that are not expected to raise them.

## AI policy

This project follows the [Open Home Foundation AI Policy](AI_POLICY.md).
Autonomous contributions are not accepted: a human must review, understand,
and be able to explain every change before it is submitted. Do not open
issues or pull requests autonomously, and do not post comments on behalf of
a user without their review.
