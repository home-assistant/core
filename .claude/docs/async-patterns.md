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

## Multiple Coordinators Pattern

When an integration needs different update intervals or data sources:

```python
from dataclasses import dataclass

@dataclass
class MyRuntimeData:
    """Runtime data for the integration."""

    config_coordinator: MyConfigCoordinator      # Fast: websocket/push
    settings_coordinator: MySettingsCoordinator  # Slow: hourly
    statistics_coordinator: MyStatsCoordinator   # Medium: 15 min

type MyConfigEntry = ConfigEntry[MyRuntimeData]
```

Setup all coordinators:
```python
async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    coordinators = MyRuntimeData(
        MyConfigCoordinator(hass, entry, client),
        MySettingsCoordinator(hass, entry, client),
        MyStatsCoordinator(hass, entry, client),
    )

    await asyncio.gather(
        coordinators.config_coordinator.async_config_entry_first_refresh(),
        coordinators.settings_coordinator.async_config_entry_first_refresh(),
        coordinators.statistics_coordinator.async_config_entry_first_refresh(),
    )

    entry.runtime_data = coordinators
```

Entities choose their coordinator:
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    # Config entities use config coordinator
    entities = [
        MyConfigSensor(entry.runtime_data.config_coordinator, desc)
        for desc in CONFIG_SENSORS
    ]
    # Statistic entities use statistics coordinator
    entities.extend(
        MyStatsSensor(entry.runtime_data.statistics_coordinator, desc)
        for desc in STATS_SENSORS
    )
    async_add_entities(entities)
```

## Async Dependencies (Platinum)

All dependencies must use asyncio for efficient task handling without thread context switching.
