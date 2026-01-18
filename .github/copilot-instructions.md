# Home Assistant Core

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Skills

This repository uses a skills-based approach for AI assistance. Skills are located in `.claude/skills/` and provide focused guidance for specific tasks.

### Available Skills

| Skill | Description |
|-------|-------------|
| `code-standards` | Python requirements, code style, logging, writing style |
| `create-integration` | Create a new integration from scratch |
| `write-tests` | Write and run tests for integrations |
| `config-flow` | Implement configuration flows |
| `entity` | Create and manage entities |
| `coordinator` | Implement data update coordinators |
| `quality-scale` | Understand and implement quality scale rules |
| `async-programming` | Async patterns and best practices |
| `diagnostics` | Implement diagnostics and repair issues |
| `device-discovery` | Implement device discovery (zeroconf, dhcp, bluetooth, etc.) |
| `services` | Register and implement service actions |

### When to Use Skills

- **Creating a new integration**: Start with `create-integration`, then use specific skills as needed
- **Adding a platform**: Use `entity` for entity development, `coordinator` if data fetching is needed
- **Writing tests**: Use `write-tests` for testing patterns and commands
- **Improving quality**: Use `quality-scale` to understand requirements for each tier

## Code Review Guidelines

**When reviewing code, do NOT comment on:**
- **Missing imports** - We use static analysis tooling to catch that
- **Code formatting** - We have ruff as a formatting tool that will catch those if needed (unless specifically instructed otherwise in these instructions)

**Git commit practices during review:**
- **Do NOT amend, squash, or rebase commits after review has started** - Reviewers need to see what changed since their last review

## File Locations

- Integration code: `homeassistant/components/<domain>/`
- Integration tests: `tests/components/<domain>/`
- Shared constants: `homeassistant/const.py`
