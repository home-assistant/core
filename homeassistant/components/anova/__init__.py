"""The Anova integration."""
from __future__ import annotations

import logging

from anova_wifi import AnovaApi, AnovaPrecisionCooker, InvalidLogin, NoDevicesFound

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import AnovaCoordinator
from .models import AnovaData
from .util import serialize_device_list

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
    api.existing_devices = [
        AnovaPrecisionCooker(
            aiohttp_client.async_get_clientsession(hass),
            device[0],
            device[1],
            api.jwt,
        )
        for device in entry.data["devices"]
    ]
    try:
        new_devices = await api.get_devices()
    except NoDevicesFound:
        # get_devices raises an exception if no devices are online
        new_devices = []
    devices = api.existing_devices
    if new_devices:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                **{"devices": serialize_device_list(devices)},
            },
        )
    coordinators = [AnovaCoordinator(hass, device) for device in devices]
    for coordinator in coordinators:
        await coordinator.async_config_entry_first_refresh()
        firmware_version = coordinator.data.sensor.firmware_version
        coordinator.async_setup(str(firmware_version))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = AnovaData(
        api_jwt=api.jwt, precision_cookers=devices, coordinators=coordinators
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
