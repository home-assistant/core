"""The Victron VRM Solar Forecast integration."""

from __future__ import annotations

from victron_vrm.exceptions import VictronVRMError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import (
    LOGGER,
    VictronRemoteMonitoringConfigEntry,
    VictronRemoteMonitoringDataUpdateCoordinator,
)

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> bool:
    """Set up VRM from a config entry."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    try:
        await coordinator.start_mqtt()
    except (TimeoutError, OSError, RuntimeError, VictronVRMError) as ex:
        LOGGER.error("Failed to start MQTT client: %s", ex)
        await async_unload_entry(hass, entry)
        raise

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> bool:
    """Unload a config entry."""
    coordinator: VictronRemoteMonitoringDataUpdateCoordinator = entry.runtime_data
    if coordinator.mqtt_client is not None:
        await coordinator.stop_mqtt()

    coordinator.mqtt_hub.unregister_all_new_metric_callbacks()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: VictronRemoteMonitoringConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
