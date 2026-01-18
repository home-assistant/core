# Code Standards

This skill covers coding standards that apply to all Home Assistant integration development.

## When to Use

- Writing or modifying any integration code
- Understanding code quality requirements
- Following logging and writing style conventions

## Python Requirements

- **Compatibility**: Python 3.13+
- **Language Features**: Use the newest features when possible:
  - Pattern matching
  - Type hints
  - f-strings (preferred over `%` or `.format()`)
  - Dataclasses
  - Walrus operator

## Code Quality Standards

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type Checking**: MyPy
- **Lint/Type/Format Fixes**: Always prefer addressing the underlying issue (e.g., import the typed source, update shared stubs, align with Ruff expectations, or correct formatting at the source) before disabling a rule, adding `# type: ignore`, or skipping a formatter. Treat suppressions and `noqa` comments as a last resort once no compliant fix exists
- **Testing**: pytest with plain functions and fixtures
- **Language**: American English for all code, comments, and documentation (use sentence case, including titles)

## Writing Style Guidelines

- **Tone**: Friendly and informative
- **Perspective**: Use second-person ("you" and "your") for user-facing messages
- **Inclusivity**: Use objective, non-discriminatory language
- **Clarity**: Write for non-native English speakers
- **Formatting in Messages**:
  - Use backticks for: file paths, filenames, variable names, field entries
  - Use sentence case for titles and messages (capitalize only the first word and proper nouns)
  - Avoid abbreviations when possible

## Logging

- **Format Guidelines**:
  - No periods at end of messages
  - No integration names/domains (added automatically)
  - No sensitive data (keys, tokens, passwords)
- Use debug level for non-user-facing messages
- **Use Lazy Logging**:
  ```python
  _LOGGER.debug("This is a log message with %s", variable)
  ```

## Documentation Standards

- **File Headers**: Short and concise
  ```python
  """Integration for Peblar EV chargers."""
  ```
- **Method/Function Docstrings**: Required for all
  ```python
  async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
      """Set up Peblar from a config entry."""
  ```
- **Comment Style**:
  - Use clear, descriptive comments
  - Explain the "why" not just the "what"
  - Keep code block lines under 80 characters when possible
  - Use progressive disclosure (simple explanation first, complex details later)

## Development Commands

### Code Quality & Linting
- **Run all linters on all files**: `prek run --all-files`
- **Run linters on staged files only**: `prek run`
- **PyLint on everything** (slow): `pylint homeassistant`
- **PyLint on specific folder**: `pylint homeassistant/components/my_integration`
- **MyPy type checking (whole project)**: `mypy homeassistant/`
- **MyPy on specific integration**: `mypy homeassistant/components/my_integration`

### Testing
- **Integration-specific tests** (recommended):
  ```bash
  pytest ./tests/components/<integration_domain> \
    --cov=homeassistant.components.<integration_domain> \
    --cov-report term-missing \
    --durations-min=1 \
    --durations=0 \
    --numprocesses=auto
  ```
- **Quick test of changed files**: `pytest --timeout=10 --picked`
- **Update test snapshots**: Add `--snapshot-update` to pytest command
  - ⚠️ Omit test results after using `--snapshot-update`
  - Always run tests again without the flag to verify snapshots
- **Full test suite** (AVOID - very slow): `pytest ./tests`

### Dependencies & Requirements
- **Update generated files after dependency changes**: `python -m script.gen_requirements_all`
- **Install all Python requirements**: 
  ```bash
  uv pip install -r requirements_all.txt -r requirements.txt -r requirements_test.txt
  ```
- **Install test requirements only**: 
  ```bash
  uv pip install -r requirements_test_all.txt -r requirements.txt
  ```

### Translations
- **Update translations after strings.json changes**: 
  ```bash
  python -m script.translations develop --all
  ```

### Project Validation
- **Run hassfest** (checks project structure and updates generated files): 
  ```bash
  python -m script.hassfest
  ```

## File Locations

- **Integration code**: `./homeassistant/components/<integration_domain>/`
- **Integration tests**: `./tests/components/<integration_domain>/`
- Shared constants: `homeassistant/const.py` (use these instead of hardcoding)

## Related Skills

- `create-integration` - Creating new integrations
- `write-tests` - Testing patterns
- `quality-scale` - Quality requirements
