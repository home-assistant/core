"""The Broadlink integration."""
from collections import namedtuple
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_TIMEOUT,
    CONF_TYPE,
)
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_TIMEOUT, DOMAIN
from .device import BroadlinkDevice
from .helpers import mac_address

LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Inclusive(CONF_MAC, "manual_config"): mac_address,
        vol.Inclusive(CONF_TYPE, "manual_config"): cv.positive_int,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

DOMAIN_SCHEMA = vol.Schema(
    {vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])}
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: DOMAIN_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Broadlink integration."""
    config = config.get(DOMAIN, {})
    devices = config.get(CONF_DEVICES, {})

    SharedData = namedtuple("SharedData", ["devices", "platforms"])
    hass.data[DOMAIN] = SharedData({}, {})

    configured_hosts = {
        entry.data.get(CONF_HOST) for entry in hass.config_entries.async_entries(DOMAIN)
    }

    for device in devices:
        if device[CONF_HOST] in configured_hosts:
            continue

        import_device = hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=device,
        )
        hass.async_create_task(import_device)

    return True


async def async_setup_entry(hass, entry):
    """Set up a Broadlink device from a config entry."""
    device = BroadlinkDevice(hass, entry)
    return await device.async_setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    device = hass.data[DOMAIN].devices.pop(entry.entry_id)
    return await device.async_unload()
