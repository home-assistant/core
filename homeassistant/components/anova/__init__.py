"""The Anova integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from anova_wifi import (
    AnovaApi,
    APCWifiDevice,
    InvalidLogin,
    NoDevicesFound,
    WebsocketFailure,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
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
    except NoDevicesFound as err:
        # Can later setup successfully and spawn a repair.
        raise ConfigEntryNotReady(
            "No devices were found on the websocket, perhaps you don't have any devices on this account?"
        ) from err
    except WebsocketFailure as err:
        raise ConfigEntryNotReady("Failed connecting to the websocket.") from err
    # Create a coordinator per device, if the device is offline, no data will be on the
    # websocket, and the coordinator should auto mark as unavailable. But as long as
    # the websocket successfully connected, config entry should setup.
    devices: list[APCWifiDevice] = []
    if TYPE_CHECKING:
        # api.websocket_handler can't be None after successfully creating the
        # websocket client
        assert api.websocket_handler is not None
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
