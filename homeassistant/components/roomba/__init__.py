"""The roomba component."""
import logging

import async_timeout
from roomba import Roomba, RoombaConnectionError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from .const import CONF_CERT, CONF_CONTINUOUS, CONF_DELAY, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the roomba environment."""
    if DOMAIN not in config:
        return True

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )


async def async_setup_entry(hass, config_entry):
    """Set the config entry up."""
    # Set up roomba platforms with config entry
    if config_entry.data is None:
        return False

    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                "certificate": config_entry.data[CONF_CERT],
                "continuous": config_entry.data[CONF_CONTINUOUS],
                "delay": config_entry.data[CONF_DELAY],
            },
        )

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if "roomba" not in hass.data[DOMAIN]:
        roomba = Roomba(
            address=config_entry.data[CONF_HOST],
            blid=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            cert_name=config_entry.options[CONF_CERT],
            continuous=config_entry.options[CONF_CONTINUOUS],
            delay=config_entry.options[CONF_DELAY],
        )
        hass.data[DOMAIN]["roomba"] = roomba
        try:
            with async_timeout.timeout(9):
                await hass.async_add_job(roomba.connect)
        except RoombaConnectionError:
            _LOGGER.error("Error to connect to %s", config_entry.data[CONF_HOST])
            return False

    hass.data[DOMAIN]["name"] = config_entry.data[CONF_NAME]
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "vacuum")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "vacuum")
    roomba = hass.data[DOMAIN]["roomba"]
    await hass.async_add_job(roomba.disconnect)
    return True
