# Async Programming

This skill covers async patterns and best practices for Home Assistant integrations.

## When to Use

- Working with I/O operations (network, file, database)
- Understanding thread safety and event loop
- Optimizing performance of async code

## Core Principles

All external I/O operations must be async. Never block the event loop.

## Async Best Practices

### Do

```python
# Use async for I/O
data = await client.async_get_data()

# Use asyncio.sleep instead of time.sleep
await asyncio.sleep(5)

# Use gather for concurrent operations
results = await asyncio.gather(
    client.async_get_data(),
    client.async_get_status(),
)
```

### Don't

```python
# Blocking HTTP calls
data = requests.get(url)  # Blocks event loop

# Blocking sleep
time.sleep(5)  # Blocks event loop

# Await in loop (inefficient)
for item in items:
    result = await process(item)  # Do this with gather instead
```

## Executor for Blocking Operations

When you must use blocking I/O:

```python
# Wrap blocking calls in executor
result = await hass.async_add_executor_job(blocking_function, arg1, arg2)

# Example with file operations
content = await hass.async_add_executor_job(pathlib.Path(path).read_text)

# Example with sync library
data = await hass.async_add_executor_job(sync_client.get_data)
```

## Thread Safety

### @callback Decorator

For functions that are safe to run in the event loop:

```python
from homeassistant.core import callback

@callback
def async_update_callback(self, event):
    """Handle event in event loop."""
    self.async_write_ha_state()
```

### Registry Changes

Must be done in event loop thread:

```python
# Called from event loop - OK
device_registry.async_update_device(device_id, ...)

# From executor job - use async version
await hass.async_add_executor_job(sync_operation)
# Then update registry after returning to event loop
```

## WebSession Injection (Platinum)

Pass web sessions to dependencies for efficiency:

```python
from homeassistant.helpers.aiohttp_client import async_get_clientsession

async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
) -> bool:
    """Set up integration from config entry."""
    session = async_get_clientsession(hass)
    client = MyClient(entry.data[CONF_HOST], session)
    entry.runtime_data = client
    return True
```

For cookies or custom configuration:

```python
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.httpx_client import create_async_httpx_client

# aiohttp with cookies
session = async_create_clientsession(hass)

# httpx client
client = create_async_httpx_client(hass)
```

## Async Dependencies (Platinum)

All dependencies should use asyncio for efficient task handling.

## Await in Loops

Replace sequential awaits with `gather`:

```python
# Bad - sequential, slow
results = []
for item in items:
    result = await process(item)
    results.append(result)

# Good - concurrent, fast
results = await asyncio.gather(
    *(process(item) for item in items)
)
```

## Executor Job Grouping

Switching between event loop and executor is expensive:

```python
# Bad - multiple switches
data1 = await hass.async_add_executor_job(get_data1)
data2 = await hass.async_add_executor_job(get_data2)
data3 = await hass.async_add_executor_job(get_data3)

# Good - single switch
def get_all_data():
    return get_data1(), get_data2(), get_data3()

data1, data2, data3 = await hass.async_add_executor_job(get_all_data)
```

## Event Subscriptions

Subscribe in `async_added_to_hass`, clean up properly:

```python
async def async_added_to_hass(self) -> None:
    """Subscribe to events when added to hass."""
    await super().async_added_to_hass()
    self.async_on_remove(
        async_track_state_change_event(
            self.hass,
            self._entities,
            self._handle_state_change,
        )
    )
```

## Background Tasks

For long-running operations:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up integration."""

    async def async_background_task():
        """Run background task."""
        try:
            while True:
                await asyncio.sleep(60)
                await do_periodic_work()
        except Exception:  # Allowed in background tasks
            _LOGGER.exception("Unexpected error in background task")

    entry.async_create_background_task(
        hass,
        async_background_task(),
        "my_integration_background_task",
    )
    return True
```

## Bluetooth Connections

Never reuse `BleakClient` instances:

```python
# Bad - reusing client
self.client = BleakClient(address)
await self.client.connect()
# Later...
await self.client.connect()  # Don't reuse

# Good - fresh instance each time
async with BleakClient(address) as client:
    data = await client.read_gatt_char(UUID)
```

Use 10+ second timeouts for Bluetooth operations.

## Zeroconf/mDNS

Use async instances:

```python
aiozc = await zeroconf.async_get_async_instance(hass)
```

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

### When Bare Exceptions Are Allowed

```python
# In config flows (for robustness)
async def async_step_user(self, user_input=None):
    try:
        await self._test_connection(user_input)
    except Exception:  # Allowed here
        errors["base"] = "unknown"

# In background tasks
async def _background_refresh():
    try:
        await coordinator.async_refresh()
    except Exception:  # Allowed in tasks
        _LOGGER.exception("Unexpected error")
```

## Related Skills

- `coordinator` - Async data fetching patterns
- `device-discovery` - Async discovery handlers
