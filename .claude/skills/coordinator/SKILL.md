# Data Update Coordinator

This skill covers implementing data update coordinators for efficient data fetching.

## When to Use

- Fetching data from devices or APIs that multiple entities share
- Implementing polling-based updates
- Centralizing error handling for data fetching

## Basic Coordinator

```python
class MyCoordinator(DataUpdateCoordinator[MyData]):
    def __init__(self, hass: HomeAssistant, client: MyClient, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # ✅ Pass config_entry - it's accepted and recommended
        )
        self.client = client

    async def _async_update_data(self):
        try:
            return await self.client.fetch_data()
        except ApiError as err:
            raise UpdateFailed(f"API communication error: {err}")
```

## Error Types

- **UpdateFailed**: API/connection errors (temporary)
- **ConfigEntryAuthFailed**: Authentication issues (triggers reauth flow)

## Config Entry

Always pass `config_entry` parameter to coordinator - it's accepted and recommended.

## Polling Intervals

**Polling intervals are NOT user-configurable.**

Never add scan_interval, update_interval, or polling frequency options to config flows or config entries.

**Integration determines intervals**: Set `update_interval` programmatically based on integration logic, not user input.

```python
# Good - integration determines interval based on device type
interval = timedelta(minutes=1) if client.is_local else timedelta(minutes=5)
```

### Minimum Intervals

- Local network: 5 seconds
- Cloud services: 60 seconds

## Parallel Updates

Specify number of concurrent updates:

```python
PARALLEL_UPDATES = 1  # Serialize updates to prevent overwhelming device
# OR
PARALLEL_UPDATES = 0  # Unlimited (for coordinator-based or read-only)
```

## Unavailability Logging

Log once when unavailable, once when recovered:

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

## Related Skills

- `entity` - Using coordinator in entities
- `async-programming` - Async best practices
- `write-tests` - Testing coordinator behavior
