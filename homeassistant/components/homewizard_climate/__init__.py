"""The Homewizard Climate integration."""
from __future__ import annotations

import logging

from homewizard_climate_websocket.api.api import (
    HomeWizardClimateApi,
    InvalidHomewizardAuth,
)
from homewizard_climate_websocket.model.climate_device import HomeWizardClimateDevice
from homewizard_climate_websocket.ws.hw_websocket import HomeWizardClimateWebSocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewizard Climate from a config entry."""

    api: HomeWizardClimateApi = HomeWizardClimateApi(
        entry.data.get(CONF_USERNAME), entry.data.get(CONF_PASSWORD)
    )

    try:
        await hass.async_add_executor_job(api.login)
    except InvalidHomewizardAuth as exc:
        raise ConfigEntryAuthFailed from exc

    devices: list[HomeWizardClimateDevice] = await hass.async_add_executor_job(
        api.get_devices
    )
    websockets = []
    for device in devices:
        websocket: HomeWizardClimateWebSocket = HomeWizardClimateWebSocket(
            api,
            device,
        )
        websocket.connect_in_thread()
        websockets.append(websocket)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["websockets"] = websockets

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for websocket in hass.data[DOMAIN][entry.entry_id]["websockets"]:
        websocket.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
