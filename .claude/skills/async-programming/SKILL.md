# Async Programming

This skill covers async patterns and best practices for Home Assistant integrations.

## When to Use

- Working with I/O operations (network, file, database)
- Understanding thread safety and event loop
- Optimizing performance of async code

## Core Principles

All external I/O operations must be async. Never block the event loop.

## Best Practices

- Avoid sleeping in loops
- Avoid awaiting in loops - use `gather` instead
- No blocking calls
- Group executor jobs when possible - switching between event loop and executor is expensive

## Blocking Operations

Use executor for blocking I/O operations:

```python
result = await hass.async_add_executor_job(blocking_function, args)
```

**Never Block Event Loop**: Avoid file operations, `time.sleep()`, blocking HTTP calls.

**Replace with Async**: Use `asyncio.sleep()` instead of `time.sleep()`.

## Thread Safety

### @callback Decorator

For event loop safe functions:

```python
@callback
def async_update_callback(self, event):
    """Safe to run in event loop."""
    self.async_write_ha_state()
```

### Sync APIs from Threads

Use sync versions when calling from non-event loop threads.

### Registry Changes

Must be done in event loop thread.

## WebSession Injection (Platinum)

Pass web sessions to dependencies:

```python
async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Set up integration from config entry."""
    client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
```

For cookies: Use `async_create_clientsession` (aiohttp) or `create_async_httpx_client` (httpx).

## Async Dependencies (Platinum)

All dependencies must use asyncio for efficient task handling without thread context switching.

## Common Anti-Patterns

### Don't Do This

```python
# Blocking HTTP calls
data = requests.get(url)  # Blocks event loop

# Blocking sleep
time.sleep(5)  # Blocks event loop

# Await in loop (inefficient)
results = []
for item in items:
    result = await process(item)  # Sequential, slow
    results.append(result)

# Too much in try block
try:
    data = await client.get_data()
    # Processing should be outside try
    processed = data["value"] * 100
    self._attr_native_value = processed
except ClientError:
    _LOGGER.error("Failed")

# Bare exceptions (usually not allowed)
try:
    value = await sensor.read()
except Exception:  # Too broad
    pass
```

### Do This Instead

```python
# Use executor for blocking calls
data = await hass.async_add_executor_job(requests.get, url)

# Async sleep
await asyncio.sleep(5)

# Use gather for concurrent operations
results = await asyncio.gather(
    *(process(item) for item in items)
)

# Minimal try blocks
try:
    data = await client.get_data()
except ClientError:
    _LOGGER.error("Failed")
    return

# Process outside try block
processed = data["value"] * 100
self._attr_native_value = processed

# Catch specific exceptions
try:
    value = await sensor.read()
except (ConnectionError, TimeoutError) as err:
    _LOGGER.warning("Read failed: %s", err)
```

## Bare Exception Rules

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

## Setup Failure Patterns

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
