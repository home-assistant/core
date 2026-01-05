# Anti-Patterns and Best Practices

## Blocking Operations

```python
# ❌ Bad - blocks event loop
data = requests.get(url)
time.sleep(5)

# ✅ Good - async operations
data = await hass.async_add_executor_job(requests.get, url)
await asyncio.sleep(5)
```

## BleakClient Reuse

```python
# ❌ Bad - reusing client
self.client = BleakClient(address)
await self.client.connect()
# Later...
await self.client.connect()  # Don't reuse!

# ✅ Good - fresh instance
client = BleakClient(address)
await client.connect()
```

## Hardcoded Strings

```python
# ❌ Bad - not translatable
self._attr_name = "Temperature Sensor"

# ✅ Good - translatable
_attr_translation_key = "temperature_sensor"
```

## Missing Error Handling

```python
# ❌ Bad - no exception handling
data = await self.api.get_data()

# ✅ Good - proper handling
try:
    data = await self.api.get_data()
except ApiException as err:
    raise UpdateFailed(f"API error: {err}") from err
```

## Sensitive Data in Diagnostics

```python
# ❌ Bad - exposes secrets
return {"api_key": entry.data[CONF_API_KEY]}

# ✅ Good - redacted
return async_redact_data(data, {"api_key", "password"})
```

## Accessing hass.data in Tests

```python
# ❌ Bad - direct access
coordinator = hass.data[DOMAIN][entry.entry_id]

# ✅ Good - proper fixture setup
@pytest.fixture
async def init_integration(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
```

## User-Configurable Polling

```python
# ❌ Bad - user controls interval
vol.Optional("scan_interval", default=60): cv.positive_int
update_interval = timedelta(minutes=entry.data.get("scan_interval", 1))

# ✅ Good - integration determines interval
SCAN_INTERVAL = timedelta(minutes=5)
interval = timedelta(minutes=1) if client.is_local else SCAN_INTERVAL
```

## User-Configurable Names

```python
# ❌ Bad - user sets name in config flow (non-helper)
vol.Optional("name", default="My Device"): cv.string

# ✅ Good - names auto-generated or set in UI later
# Don't add name field to config flow
```

## Too Much in Try Block

```python
# ❌ Bad - processing inside try
try:
    response = await client.get_data()
    temperature = response["temperature"] / 10
    self._attr_native_value = temperature
except ClientError:
    _LOGGER.error("Failed to fetch data")

# ✅ Good - minimal try block
try:
    response = await client.get_data()
except ClientError:
    _LOGGER.error("Failed to fetch data")
    return

temperature = response["temperature"] / 10
self._attr_native_value = temperature
```

## Bare Exceptions

```python
# ❌ Bad - in regular code
try:
    value = await sensor.read_value()
except Exception:
    _LOGGER.error("Failed to read sensor")

# ✅ OK - in config flow (for robustness)
async def async_step_user(self, user_input=None):
    try:
        await self._test_connection(user_input)
    except Exception:
        errors["base"] = "unknown"

# ✅ OK - in background tasks
async def _background_refresh():
    try:
        await coordinator.async_refresh()
    except Exception:
        _LOGGER.exception("Unexpected error in background task")
```

## Logging Anti-Patterns

```python
# ❌ Bad
_LOGGER.debug("Processing data.")  # No period
_LOGGER.debug("[my_integration] Processing")  # No domain prefix
_LOGGER.debug("API key: %s", api_key)  # No sensitive data
_LOGGER.debug("Processing data: " + str(data))  # Use lazy logging

# ✅ Good
_LOGGER.debug("Processing data: %s", data)
```

## Entity Lifecycle

```python
# ❌ Bad - subscribing in __init__
def __init__(self):
    self.client.subscribe(self._handle_event)

# ✅ Good - subscribing in async_added_to_hass
async def async_added_to_hass(self) -> None:
    self.async_on_remove(
        self.client.subscribe(self._handle_event)
    )
```

## State Values

```python
# ❌ Bad - string for unknown
self._attr_native_value = "unknown"

# ✅ Good - None for unknown
self._attr_native_value = None
```

## Unique ID Sources

```python
# ❌ Bad - unstable identifiers
self._attr_unique_id = device.ip_address
self._attr_unique_id = device.name
self._attr_unique_id = user.email

# ✅ Good - stable identifiers
self._attr_unique_id = device.serial_number
self._attr_unique_id = format_mac(device.mac)
self._attr_unique_id = f"{entry.entry_id}-battery"  # Last resort
```

## Coordinator Setup

```python
# ❌ Bad - missing config_entry
super().__init__(
    hass,
    logger=LOGGER,
    name=DOMAIN,
    update_interval=timedelta(minutes=5),
)

# ✅ Good - pass config_entry
super().__init__(
    hass,
    logger=LOGGER,
    name=DOMAIN,
    update_interval=timedelta(minutes=5),
    config_entry=config_entry,
)
```
