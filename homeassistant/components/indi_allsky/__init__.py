"""The INDI Allsky integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import IndiAllSkyConfigEntry, IndiAllSkyDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: IndiAllSkyConfigEntry) -> bool:
    """Set up INDI Allsky from a config entry."""
    coordinator = IndiAllSkyDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    ws_task = hass.async_create_background_task(
        coordinator.client.listen(auto_reconnect=True),
        "indi_allsky_ws_events",
    )

    def _cancel_ws_task() -> None:
        ws_task.cancel()

    entry.async_on_unload(_cancel_ws_task)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IndiAllSkyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.disconnect()
    return unload_ok
