"""Support for EnOcean devices."""

import voluptuous as vol

from homeassistant.components.enocean.const import DATA_ENOCEAN, DOMAIN, LOGGER
from homeassistant.components.enocean.dongle import EnOceanDongle
from homeassistant.const import CONF_DEVICE
import homeassistant.helpers.config_validation as cv

from ... import config_entries, core

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass, config):
    """Set up the EnOcean component."""
    LOGGER.debug("setup with config")

    # support for text-based configuration (legacy)
    if DOMAIN in config:
        serial_dev = config[DOMAIN].get(CONF_DEVICE)
        enocean_dongle = EnOceanDongle(hass, serial_dev)
        hass.data[DATA_ENOCEAN] = enocean_dongle

    return True


async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Set up an EnOcean dongle for the given entry.

    This will read a flow-based configuration, but only if
    a configuration was not found in the text-based configuration.
    """
    LOGGER.debug("async setup")

    if DATA_ENOCEAN in hass.data and hass.data[DATA_ENOCEAN] is EnOceanDongle:
        LOGGER.debug("  dongle already configured, skipping")
        return True

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if CONF_DEVICE not in config_entry.data:
        LOGGER.error("Missing %s entry in config", CONF_DEVICE)
        return False

    usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    hass.data[DATA_ENOCEAN] = usb_dongle

    return True


async def async_unload_entry(hass, config_entry):
    """Unload ENOcean config entry."""
    LOGGER.debug("Unloading %s", DOMAIN)
    return True
