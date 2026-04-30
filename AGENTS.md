# GitHub Copilot & Claude Code Instructions

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Git Commit Guidelines

- **Do NOT amend, squash, or rebase commits that have already been pushed to the PR branch after the PR is opened** - Reviewers need to follow the commit history, as well as see what changed since their last review

## Development Commands

.vscode/tasks.json contains useful commands used for development.

## Python Syntax Notes

- Home Assistant officially supports Python 3.14 as its minimum version. Do not flag syntax or features that require Python 3.14 as issues, and do not suggest workarounds for older Python versions.
- Python 3.14 explicitly allows `except TypeA, TypeB:` without parentheses. Never flag this as an issue.
- Python 3.14 evaluates annotations lazily (PEP 649). Forward references in annotations do not need to be quoted — annotations can reference names defined later in the module without quoting them or using `from __future__ import annotations`. Do not flag unquoted forward references in annotations as issues.

## Testing

When writing or modifying tests, ensure all test function parameters have type annotations.
Prefer concrete types (for example, `HomeAssistant`, `MockConfigEntry`, etc.) over `Any`.

## Good practices

Integrations with Platinum or Gold level in the Integration Quality Scale reflect a high standard of code quality and maintainability. When looking for examples of something, these are good places to start. The level is indicated in the manifest.json of the integration.

When reviewing entity actions, do not suggest extra defensive checks for input fields that are already validated by Home Assistant's service/action schemas and entity selection filters. Suggest additional guards only when data bypasses those validators or is transformed into a less-safe form.
When validation guarantees a dict key exists, prefer direct key access (`data["key"]`) instead of `.get("key")` so contract violations are surfaced instead of silently masked.
