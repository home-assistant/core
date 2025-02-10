# Instructions for GitHub Copilot

This repository holds the core of Home Assistant, a Python 3 based home
automation application.

- Python code must be compatible with Python 3.13
- Use the newest Python language features if possible:
  - Pattern matching
  - Type hints
  - f-strings for string formatting over `%` or `.format()`
  - Dataclasses
  - Walrus operator
- Code quality tools:
  - Formatting: Ruff
  - Linting: PyLint and Ruff
  - Type checking: MyPy
  - Testing: pytest with plain functions and fixtures
- Inline code documentation:
  - File headers should be short and concise:
    ```python
    """Integration for Peblar EV chargers."""
    ```
  - Every method and function needs a docstring:
    ```python
    async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
        """Set up Peblar from a config entry."""
        ...
    ```
- All code and comments and other text are written in American English
- Follow existing code style patterns as much as possible
- Core locations:
  - Shared constants: `homeassistant/const.py`, use them instead of hardcoding
    strings or creating duplicate integration constants.
  - Integration files:
    - Constants: `homeassistant/components/{domain}/const.py`
    - Models: `homeassistant/components/{domain}/models.py`
    - Coordinator: `homeassistant/components/{domain}/coordinator.py`
    - Config flow: `homeassistant/components/{domain}/config_flow.py`
    - Platform code: `homeassistant/components/{domain}/{platform}.py`
- All external I/O operations must be async
- Async patterns:
  - Avoid sleeping in loops
  - Avoid awaiting in loops, gather instead
  - No blocking calls
- Polling:
  - Follow update coordinator pattern, when possible
  - Polling interval may not be configurable by the user
  - For local network polling, the minimum interval is 5 seconds
  - For cloud polling, the minimum interval is 60 seconds
- Error handling:
  - Use specific exceptions from `homeassistant.exceptions`
  - Setup failures:
    - Temporary: Raise `ConfigEntryNotReady`
    - Permanent: Use `ConfigEntryError`
- Logging:
  - Message format:
    - No periods at end
    - No integration names or domains (added automatically)
    - No sensitive data (keys, tokens, passwords), even when those are incorrect.
  - Be very restrictive on the use of logging info messages, use debug for
    anything which is not targeting the user.
  - Use lazy logging (no f-strings):
    ```python
    _LOGGER.debug("This is a log message with %s", variable)
    ```
- Entities:
  - Ensure unique IDs for state persistence:
    - Unique IDs should not contain values that are subject to user or network change.
    - An ID needs to be unique per platform, not per integration.
    - The ID does not have to contain the integration domain or platform.
    - Acceptable examples:
      - Serial number of a device
      - MAC address of a device formatted using `homeassistant.helpers.device_registry.format_mac`
        Do not obtain the MAC address through arp cache of local network access,
        only use the MAC address provided by discovery or the device itself.
      - Unique identifier that is physically printed on the device or burned into an EEPROM
    - Not acceptable examples:
      - IP Address
      - Device name
      - Hostname
      - URL
      - Email address
      - Username
    - For entities that are setup by a config entry, the config entry ID
      can be used as a last resort if no other Unique ID is available.
      For example: `f"{entry.entry_id}-battery"`
  - If the state value is unknown, use `None`
  - Do not use the `unavailable` string as a state value,
    implement the `available()` property method instead
  - Do not use the `unknown` string as a state value, use `None` instead
- Extra entity state attributes:
  - The keys of all state attributes should always be present
  - If the value is unknown, use `None`
  - Provide descriptive state attributes
- Testing:
  - Test location: `tests/components/{domain}/`
  - Use pytest fixtures from `tests.common`
  - Mock external dependencies
  - Use snapshots for complex data
  - Follow existing test patterns
