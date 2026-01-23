---
title: "Handling setup failures"
---

Your integration may not be able to be set up for a variety of reasons. The most common cases are because the device or service is offline or the credentials are no longer valid. Your integration must retry setup so it can recover as soon as reasonably possible when the device or service is back online without the user having to restart Home Assistant.

## Handling offline or unavailable devices and services

### Integrations using `async_setup_entry`

Raise the `ConfigEntryNotReady` exception from `async_setup_entry` in the integration's `__init__.py`, and Home Assistant will automatically take care of retrying set up later. To avoid doubt, raising `ConfigEntryNotReady` in a platform's `async_setup_entry` is ineffective because it is too late to be caught by the config entry setup.

#### Example

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup the config entry for my device."""
    device = MyDevice(entry.data[CONF_HOST])
    try:
        await device.async_setup()
    except (asyncio.TimeoutError, TimeoutException) as ex:
        raise ConfigEntryNotReady(f"Timeout while connecting to {device.ipaddr}") from ex
```

If you are using a [DataUpdateCoordinator](integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities), calling `await coordinator.async_config_entry_first_refresh()` will also trigger this exception automatically if the first refresh failed.

If your integration supports discovery, Home Assistant will automatically retry as soon as your device or service gets discovered.

#### Handling logging of a retry

Pass the error message to `ConfigEntryNotReady` as the first argument. Home Assistant will log at `debug` level. The error message will also be propagated to the UI and shown on the integrations page. Suppose you do not set a message when raising `ConfigEntryNotReady`; in that case, Home Assistant will try to extract the reason from the exception that is the cause of `ConfigEntryNotReady` if it was propagated from another exception.

The integration should not log any non-debug messages about the retry, and should instead rely on the logic built-in to `ConfigEntryNotReady` to avoid spamming the logs.

### Integrations using `async_setup_platform`

Raise the `PlatformNotReady` exception from `async_setup_platform`, and Home Assistant will automatically take care of retrying set up later.

#### Example

```python
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform."""
    device = MyDevice(conf[CONF_HOST])
    try:
        await device.async_setup()
    except ConnectionError as ex:
        raise PlatformNotReady(f"Connection error while connecting to {device.ipaddr}: {ex}") from ex
```

#### Handling logging of a retry

Pass the error message to `PlatformNotReady` as the first argument. Home Assistant will log the retry once with a log level of
`warning`, and subsequent retries will be logged at `debug` level. Suppose you do not set a message when raising `ConfigEntryNotReady`; in that case, Home Assistant will try to extract the reason from the exception that is the cause of `ConfigEntryNotReady` if it was propagated from another exception.

The integration should not log any non-debug messages about the retry, and should instead rely on the logic built-in to `PlatformNotReady` to avoid spamming the logs.

## Handling expired credentials

Raise the `ConfigEntryAuthFailed` exception, and Home Assistant will automatically put the config entry in a failure state and start a reauth flow. The exception must be raised from `async_setup_entry` in `__init__.py` or from the `DataUpdateCoordinator` or the exception will not be effective at triggering the reauth flow. If your integration does not use a `DataUpdateCoordinator`, calling `entry.async_start_reauth()` can be used as an alternative to starting a reauth flow.

The `reauth` flow will be started with the following context variables, which are available in the `async_step_reauth` step:

- source: This will always be "SOURCE_REAUTH"
- entry_id: The entry_id of the config entry that needs reauthentication
- unique_id: The unique_id of the config entry that needs reauthentication

#### Example

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup the config entry for my device."""
    device = MyDevice(entry.data[CONF_HOST])
    try:
        await device.async_setup()
    except AuthFailed as ex:
        raise ConfigEntryAuthFailed(f"Credentials expired for {device.name}") from ex
    except (asyncio.TimeoutError, TimeoutException) as ex:
        raise ConfigEntryNotReady(f"Timed out while connecting to {device.ipaddr}") from ex
```
