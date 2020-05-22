"""Support for EnOcean devices."""

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_DEVICE
import homeassistant.helpers.config_validation as cv

from .const import DATA_ENOCEAN, DOMAIN, LOGGER
from .dongle import EnOceanDongle

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the EnOcean component."""
    # support for text-based configuration (legacy)
    if DOMAIN not in config:
        return True

    configured_dongle = {
        entry.data[CONF_DEVICE] for entry in hass.config_entries.async_entries(DOMAIN)
    }
    if configured_dongle:
        # We can only have one dongle. If there is already one in the config,
        # there is no need to import the yaml based config.
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Set up an EnOcean dongle for the given entry.

    This will read a flow-based configuration, but only if
    a configuration was not found in the text-based configuration.
    """
    if DATA_ENOCEAN in hass.data and hass.data[DATA_ENOCEAN] is EnOceanDongle:
        LOGGER.warning("Dongle already configured, skipping configuration")
        return True

    if DATA_ENOCEAN not in hass.data:
        hass.data[DATA_ENOCEAN] = {}

    usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    hass.data[DATA_ENOCEAN] = usb_dongle
    await usb_dongle.async_setup()

    return True


async def async_unload_entry(hass, config_entry):
    """Unload ENOcean config entry."""
    hass.data[DATA_ENOCEAN] = None
    return True
