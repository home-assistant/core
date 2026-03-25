# GitHub Copilot & Claude Code Instructions

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Code Review Guidelines

**Git commit practices during review:**
- **Do NOT amend, squash, or rebase commits after review has started** - Reviewers need to see what changed since their last review

## Development Commands

.vscode/tasks.json contains useful commands used for development.

## Python Syntax Notes

- Python 3.14 explicitly allows `except TypeA, TypeB:` without parentheses.

## Testing

- When writing or modifying tests, ensure all test function parameters have type annotations.
- Prefer concrete types (for example, `HomeAssistant`, `MockConfigEntry`, etc.) over `Any`.
- Add tests when they do not already exist so new behavior is covered and later changes are less likely to regress it.
- Prefer `.ambr` snapshots, mocks, and fixtures so tests are easier to extend.
- Prefer `patch.object(...)` only when it patches the same attribute reference that the code under test resolves at runtime; otherwise, patch the attribute on the module under test (the place where the name is actually looked up) so patches remain correct and easy to follow.
- If an integration grows a `setup_integration` helper, add it to `tests/components/<integration>/__init__.py` so tests can share one setup path and future contributors can extend them without duplicating setup code.
- Keep tests DRY with `pytest.mark.parametrize` where it fits so new cases can be added without copying the full test body.

## Good practices

Integrations with Platinum or Gold level in the Integration Quality Scale reflect a high standard of code quality and maintainability. When looking for examples of something, these are good places to start. The level is indicated in the manifest.json of the integration.
