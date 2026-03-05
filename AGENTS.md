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

### Documentation Standards
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

## Async Programming

- All external I/O operations must be async
- **Best Practices**:
  - Avoid sleeping in loops
  - Avoid awaiting in loops - use `gather` instead
  - No blocking calls
  - Group executor jobs when possible - switching between event loop and executor is expensive

### Blocking Operations
- **Use Executor**: For blocking I/O operations
  ```python
  result = await hass.async_add_executor_job(blocking_function, args)
  ```
- **Never Block Event Loop**: Avoid file operations, `time.sleep()`, blocking HTTP calls
- **Replace with Async**: Use `asyncio.sleep()` instead of `time.sleep()`

### Thread Safety
- **@callback Decorator**: For event loop safe functions
  ```python
  @callback
  def async_update_callback(self, event):
      """Safe to run in event loop."""
      self.async_write_ha_state()
  ```
- **Sync APIs from Threads**: Use sync versions when calling from non-event loop threads
- **Registry Changes**: Must be done in event loop thread

### Error Handling
- **Exception Types**: Choose most specific exception available
  - `ServiceValidationError`: User input errors (preferred over `ValueError`)
  - `HomeAssistantError`: Device communication failures
  - `ConfigEntryNotReady`: Temporary setup issues (device offline)
  - `ConfigEntryAuthFailed`: Authentication problems
  - `ConfigEntryError`: Permanent setup issues
- **Try/Catch Best Practices**:
  - Only wrap code that can throw exceptions
  - Keep try blocks minimal - process data after the try/catch
  - **Avoid bare exceptions** except in specific cases:
    - ❌ Generally not allowed: `except:` or `except Exception:`
    - ✅ Allowed in config flows to ensure robustness
    - ✅ Allowed in functions/methods that run in background tasks
  - Bad pattern:
    ```python
    try:
        data = await device.get_data()  # Can throw
        # ❌ Don't process data inside try block
        processed = data.get("value", 0) * 100
        self._attr_native_value = processed
    except DeviceError:
        _LOGGER.error("Failed to get data")
    ```
  - Good pattern:
    ```python
    try:
        data = await device.get_data()  # Can throw
    except DeviceError:
        _LOGGER.error("Failed to get data")
        return

    # ✅ Process data outside try block
    processed = data.get("value", 0) * 100
    self._attr_native_value = processed
    ```
- **Bare Exception Usage**:
  ```python
  # ❌ Not allowed in regular code
  try:
      data = await device.get_data()
  except Exception:  # Too broad
      _LOGGER.error("Failed")

  # ✅ Allowed in config flow for robustness
  async def async_step_user(self, user_input=None):
      try:
          await self._test_connection(user_input)
      except Exception:  # Allowed here
          errors["base"] = "unknown"

  # ✅ Allowed in background tasks
  async def _background_refresh():
      try:
          await coordinator.async_refresh()
      except Exception:  # Allowed in task
          _LOGGER.exception("Unexpected error in background task")
  ```
- **Setup Failure Patterns**:
  ```python
  try:
      await device.async_setup()
  except (asyncio.TimeoutError, TimeoutException) as ex:
      raise ConfigEntryNotReady(f"Timeout connecting to {device.host}") from ex
  except AuthFailed as ex:
      raise ConfigEntryAuthFailed(f"Credentials expired for {device.name}") from ex
  ```

### Logging
- **Format Guidelines**:
  - No periods at end of messages
  - No integration names/domains (added automatically)
  - No sensitive data (keys, tokens, passwords)
- Use debug level for non-user-facing messages
- **Use Lazy Logging**:
  ```python
  _LOGGER.debug("This is a log message with %s", variable)
  ```

### Unavailability Logging
- **Log Once**: When device/service becomes unavailable (info level)
- **Log Recovery**: When device/service comes back online
- **Implementation Pattern**:
  ```python
  _unavailable_logged: bool = False

  if not self._unavailable_logged:
      _LOGGER.info("The sensor is unavailable: %s", ex)
      self._unavailable_logged = True
  # On recovery:
  if self._unavailable_logged:
      _LOGGER.info("The sensor is back online")
      self._unavailable_logged = False
  ```

## Development Commands

### Environment
- **Local development (non-container)**: Activate the project venv before running commands: `source .venv/bin/activate`
- **Dev container**: No activation needed, the environment is pre-configured

### Code Quality & Linting
- **Run all linters on all files**: `prek run --all-files`
- **Run linters on staged files only**: `prek run`
- **PyLint on everything** (slow): `pylint homeassistant`
- **PyLint on specific folder**: `pylint homeassistant/components/my_integration`
- **MyPy type checking (whole project)**: `mypy homeassistant/`
- **MyPy on specific integration**: `mypy homeassistant/components/my_integration`

### Testing
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

## Common Anti-Patterns & Best Practices

### ❌ **Avoid These Patterns**
```python
# Blocking operations in event loop
data = requests.get(url)  # ❌ Blocks event loop
time.sleep(5)  # ❌ Blocks event loop

# Reusing BleakClient instances
self.client = BleakClient(address)
await self.client.connect()
# Later...
await self.client.connect()  # ❌ Don't reuse

# Hardcoded strings in code
self._attr_name = "Temperature Sensor"  # ❌ Not translatable

# Missing error handling
data = await self.api.get_data()  # ❌ No exception handling

# Storing sensitive data in diagnostics
return {"api_key": entry.data[CONF_API_KEY]}  # ❌ Exposes secrets

# Accessing hass.data directly in tests
coordinator = hass.data[DOMAIN][entry.entry_id]  # ❌ Don't access hass.data

# User-configurable polling intervals
# In config flow
vol.Optional("scan_interval", default=60): cv.positive_int  # ❌ Not allowed
# In coordinator
update_interval = timedelta(minutes=entry.data.get("scan_interval", 1))  # ❌ Not allowed

# User-configurable config entry names (non-helper integrations)
vol.Optional("name", default="My Device"): cv.string  # ❌ Not allowed in regular integrations

# Too much code in try block
try:
    response = await client.get_data()  # Can throw
    # ❌ Data processing should be outside try block
    temperature = response["temperature"] / 10
    humidity = response["humidity"]
    self._attr_native_value = temperature
except ClientError:
    _LOGGER.error("Failed to fetch data")

# Bare exceptions in regular code
try:
    value = await sensor.read_value()
except Exception:  # ❌ Too broad - catch specific exceptions
    _LOGGER.error("Failed to read sensor")
```

### ✅ **Use These Patterns Instead**
```python
# Async operations with executor
data = await hass.async_add_executor_job(requests.get, url)
await asyncio.sleep(5)  # ✅ Non-blocking

# Fresh BleakClient instances
client = BleakClient(address)  # ✅ New instance each time
await client.connect()

# Translatable entity names
_attr_translation_key = "temperature_sensor"  # ✅ Translatable

# Proper error handling
try:
    data = await self.api.get_data()
except ApiException as err:
    raise UpdateFailed(f"API error: {err}") from err

# Redacted diagnostics data
return async_redact_data(data, {"api_key", "password"})  # ✅ Safe

# Test through proper integration setup and fixtures
@pytest.fixture
async def init_integration(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)  # ✅ Proper setup

# Integration-determined polling intervals (not user-configurable)
SCAN_INTERVAL = timedelta(minutes=5)  # ✅ Common pattern: constant in const.py

class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        # ✅ Integration determines interval based on device capabilities, connection type, etc.
        interval = timedelta(minutes=1) if client.is_local else SCAN_INTERVAL
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=interval,
            config_entry=config_entry,  # ✅ Pass config_entry - it's accepted and recommended
        )
```
