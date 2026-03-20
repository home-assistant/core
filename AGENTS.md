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

When writing or modifying tests, ensure all test function parameters have type annotations.
Prefer concrete types (for example, `HomeAssistant`, `MockConfigEntry`, etc.) over `Any`.

## Pull Requests

When creating PRs with `gh pr create`, always read `.github/PULL_REQUEST_TEMPLATE.md` and use its full content as the `--body`. Keep ALL HTML comments and metadata intact — the template explicitly says "DO NOT DELETE ANY TEXT from this template!". Only fill in the relevant sections and check the appropriate boxes. Exception: the "Breaking change" section should be removed if the PR is not a breaking change (the template itself instructs this).

## Good practices

Integrations with Platinum or Gold level in the Integration Quality Scale reflect a high standard of code quality and maintainability. When looking for examples of something, these are good places to start. The level is indicated in the manifest.json of the integration.
