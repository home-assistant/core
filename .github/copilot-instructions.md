
# GitHub Copilot & Claude Code Instructions

This repository contains the core of Home Assistant, a Python 3 based home automation application.

## Code Review Guidelines

**When reviewing code, do NOT comment on:**
- **Missing imports** - We use static analysis tooling to catch that
- **Code formatting** - We have ruff as a formatting tool that will catch those if needed (unless specifically instructed otherwise in these instructions)

**Git commit practices during review:**
- **Do NOT amend, squash, or rebase commits after review has started** - Reviewers need to see what changed since their last review

## Python Requirements

- **Compatibility**: Python 3.13+
- **Language Features**: Use the newest features when possible:
  - Pattern matching
  - Type hints
  - f-strings (preferred over `%` or `.format()`)
  - Dataclasses
  - Walrus operator

### Strict Typing (Platinum)
- **Comprehensive Type Hints**: Add type hints to all functions, methods, and variables
- **Custom Config Entry Types**: When using runtime_data:
  ```python
  type MyIntegrationConfigEntry = ConfigEntry[MyClient]
  ```
- **Library Requirements**: Include `py.typed` file for PEP-561 compliance

## Code Quality Standards

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type Checking**: MyPy
- **Lint/Type/Format Fixes**: Always prefer addressing the underlying issue (e.g., import the typed source, update shared stubs, align with Ruff expectations, or correct formatting at the source) before disabling a rule, adding `# type: ignore`, or skipping a formatter. Treat suppressions and `noqa` comments as a last resort once no compliant fix exists
- **Testing**: pytest with plain functions and fixtures
- **Language**: American English for all code, comments, and documentation (use sentence case, including titles)

### Writing Style Guidelines
- **Tone**: Friendly and informative
- **Perspective**: Use second-person ("you" and "your") for user-facing messages
- **Inclusivity**: Use objective, non-discriminatory language
- **Clarity**: Write for non-native English speakers
- **Formatting in Messages**:
  - Use backticks for: file paths, filenames, variable names, field entries
  - Use sentence case for titles and messages (capitalize only the first word and proper nouns)
  - Avoid abbreviations when possible

### Skill files

- ban-word-list: /.claude/skills/ban-word-list/SKILL.md
