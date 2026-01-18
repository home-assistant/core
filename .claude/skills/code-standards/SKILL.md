# Code Standards

This skill covers coding standards that apply to all Home Assistant integration development.

## When to Use

- Writing or modifying any integration code
- Understanding code quality requirements
- Following logging and writing style conventions

## Python Requirements

- **Compatibility**: Python 3.13+
- Use modern features: pattern matching, type hints, f-strings, dataclasses, walrus operator

## Code Style

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type Checking**: MyPy
- **Docstrings**: Required for all functions/methods
- **File headers**: Short and concise
  ```python
  """Integration for My Device."""
  ```

## Logging Guidelines

```python
import logging

_LOGGER = logging.getLogger(__name__)

# Use lazy logging (pass arguments, not formatted strings)
_LOGGER.debug("Fetching data from %s", host)

# No periods at end of messages
_LOGGER.info("Device connected successfully")  # Good
_LOGGER.info("Device connected successfully.")  # Bad

# No integration names (added automatically)
_LOGGER.error("Connection failed")  # Good
_LOGGER.error("my_integration: Connection failed")  # Bad

# Never log sensitive data
_LOGGER.debug("Authenticating user")  # Good
_LOGGER.debug("Using API key: %s", api_key)  # Bad

# Use debug for non-user-facing messages
_LOGGER.debug("Processing %d items", len(items))
```

## Writing Style

- Friendly and informative tone
- Use second-person ("you" and "your") for user-facing messages
- Use backticks for: file paths, filenames, variable names
- Use sentence case for titles and messages (capitalize only first word and proper nouns)
- Avoid abbreviations
- Write for non-native English speakers

## Development Commands

```bash
# Run all linters
prek run --all-files

# Run linters on staged files only
prek run

# Run integration tests (recommended)
pytest ./tests/components/<integration_domain> \
  --cov=homeassistant.components.<integration_domain> \
  --cov-report term-missing \
  --durations-min=1 \
  --durations=0 \
  --numprocesses=auto

# Quick test of changed files
pytest --timeout=10 --picked

# Type checking
mypy homeassistant/components/<integration_domain>

# Update generated files
python -m script.hassfest
python -m script.gen_requirements_all
python -m script.translations develop --all
```

## File Locations

- Integration code: `homeassistant/components/<domain>/`
- Integration tests: `tests/components/<domain>/`
- Shared constants: `homeassistant/const.py`

## Related Skills

- `create-integration` - Creating new integrations
- `write-tests` - Testing patterns
- `quality-scale` - Quality requirements
