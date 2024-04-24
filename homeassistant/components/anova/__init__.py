"""The Anova integration."""

from __future__ import annotations

import logging

from anova_wifi import AnovaApi, APCWifiDevice, InvalidLogin, NoDevicesFound

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import AnovaCoordinator
from .models import AnovaData

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anova from a config entry."""
    api = AnovaApi(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await api.authenticate()
    except InvalidLogin as err:
        _LOGGER.error(
            "Login was incorrect - please log back in through the config flow. %s", err
        )
        return False
    assert api.jwt
    try:
        await api.create_websocket()
    except NoDevicesFound:
        _LOGGER.warning(
            "No devices were found on the websocket, perhaps you don't have any devices on this account?"
        )
    # Create a coordinator per device, if the device is offline, no data will be on the
    # websocket, and the coordinator should auto mark as unavailable. But as long as the
    # websocket successfully connected, config entry should setup.
    devices: list[APCWifiDevice] = []
    if api.websocket_handler is not None:
        devices = list(api.websocket_handler.devices.values())
    coordinators = [AnovaCoordinator(hass, device) for device in devices]
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = AnovaData(
        api_jwt=api.jwt, coordinators=coordinators, api=api
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        anova_data: AnovaData = hass.data[DOMAIN].pop(entry.entry_id)
        # Disconnect from WS
        await anova_data.api.disconnect_websocket()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if config_entry.version == 1:
        # It used to be needed to persist devices, however that is no longer the case as the
        # websocket holds information for all devices on the account.
        new = {
            CONF_USERNAME: config_entry.data[CONF_USERNAME],
            CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
        }

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    return True
