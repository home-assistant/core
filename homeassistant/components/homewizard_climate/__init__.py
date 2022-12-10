"""The Homewizard Climate integration."""
from __future__ import annotations

from homewizard_climate_websocket.api.api import HomeWizardClimateApi
from homewizard_climate_websocket.model.climate_device import HomeWizardClimateDevice
from homewizard_climate_websocket.ws.hw_websocket import HomeWizardClimateWebSocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PASSWORD, USERNAME

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewizard Climate from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    api: HomeWizardClimateApi = HomeWizardClimateApi(
        entry.data.get(USERNAME), entry.data.get(PASSWORD)
    )
    await hass.async_add_executor_job(api.login)

    devices: list[HomeWizardClimateDevice] = await hass.async_add_executor_job(
        api.get_devices
    )
    websockets = []
    for device in devices:
        websocket: HomeWizardClimateWebSocket = HomeWizardClimateWebSocket(api, device)
        hass.async_add_executor_job(websocket.connect)
        # hass.loop.run_in_executer(ws.connect())
        websockets.append(websocket)

    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["websockets"] = websockets

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
