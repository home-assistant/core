# Async Programming Patterns

## Core Principles

- All external I/O operations must be async
- Avoid sleeping in loops
- Avoid awaiting in loops - use `gather` instead
- No blocking calls
- Group executor jobs when possible - switching between event loop and executor is expensive

## Blocking Operations

Use executor for blocking I/O operations:
```python
result = await hass.async_add_executor_job(blocking_function, args)
```

**Never block the event loop**:
- Avoid file operations without executor
- No `time.sleep()` - use `asyncio.sleep()` instead
- No blocking HTTP calls

## Thread Safety

Use `@callback` decorator for event loop safe functions:
```python
@callback
def async_update_callback(self, event):
    """Safe to run in event loop."""
    self.async_write_ha_state()
```

- Sync APIs from threads: Use sync versions when calling from non-event loop threads
- Registry changes: Must be done in event loop thread

## Data Update Coordinator

Standard pattern for efficient data management:
```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # Always pass config_entry
        )
        self.client = client

    async def _async_update_data(self) -> MyData:
        try:
            return await self.client.fetch_data()
        except ApiError as err:
            raise UpdateFailed(f"API communication error: {err}") from err
```

**Error types**:
- `UpdateFailed`: For API errors
- `ConfigEntryAuthFailed`: For authentication issues

## WebSession Injection (Platinum)

Pass web sessions to dependencies:
```python
async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Set up integration from config entry."""
    client = MyClient(entry.data[CONF_HOST], async_get_clientsession(hass))
```

For cookies:
- aiohttp: Use `async_create_clientsession`
- httpx: Use `create_async_httpx_client`

## Async Dependencies (Platinum)

All dependencies must use asyncio for efficient task handling without thread context switching.
