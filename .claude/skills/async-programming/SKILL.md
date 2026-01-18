# Async Programming

This skill covers async patterns and best practices for Home Assistant integrations.

## When to Use

- Working with I/O operations (network, file, database)
- Understanding thread safety and event loop
- Optimizing performance of async code

## Async Programming

- All external I/O operations must be async
- **Best Practices**:
  - Avoid sleeping in loops
  - Avoid awaiting in loops - use `gather` instead
  - No blocking calls
  - Group executor jobs when possible - switching between event loop and executor is expensive

## Blocking Operations

- **Use Executor**: For blocking I/O operations
  ```python
  result = await hass.async_add_executor_job(blocking_function, args)
  ```
- **Never Block Event Loop**: Avoid file operations, `time.sleep()`, blocking HTTP calls
- **Replace with Async**: Use `asyncio.sleep()` instead of `time.sleep()`

## Thread Safety

- **@callback Decorator**: For event loop safe functions
  ```python
  @callback
  def async_update_callback(self, event):
      """Safe to run in event loop."""
      self.async_write_ha_state()
  ```
- **Sync APIs from Threads**: Use sync versions when calling from non-event loop threads
- **Registry Changes**: Must be done in event loop thread

## Async Dependencies (Platinum)

- **Requirement**: All dependencies must use asyncio
- Ensures efficient task handling without thread context switching

## WebSession Injection (Platinum)

- **Pass WebSession**: Support passing web sessions to dependencies
  ```python
  async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
      """Set up integration from config entry."""
      client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
  ```
- For cookies: Use `async_create_clientsession` (aiohttp) or `create_async_httpx_client` (httpx)

## Error Handling

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

## Related Skills

- `coordinator` - Async data fetching patterns
- `device-discovery` - Async discovery handlers
