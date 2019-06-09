"""Support for Sure Petcare cat/pet flaps."""
import logging

import voluptuous as vol
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_ICON, CONF_ID,
                                 CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_TYPE, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (CONF_FLAPS, CONF_HOUSEHOLD_ID, CONF_PETS,
                    DATA_SURE_PETCARE, DATA_SUREPY, DEFAULT_SCAN_INTERVAL,
                    DOMAIN, SURE_IDS, SureThingID)

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL

FLAP_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
})

PET_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOUSEHOLD_ID): cv.positive_int,
        vol.Optional(CONF_FLAPS): vol.Schema(
            vol.All(cv.ensure_list, [FLAP_SCHEMA])),
        vol.Optional(CONF_PETS): vol.Schema(
            vol.All(cv.ensure_list, [PET_SCHEMA])),
        vol.Optional(CONF_DEVICE_CLASS, default="door"): cv.string,
        vol.Optional(CONF_ICON, default="mdi:door"): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Sure Petcare component."""
    from surepy import SurePetcare

    # config file data
    conf = config.get(DOMAIN, dict())

    # User has configured household or flaps
    if CONF_HOUSEHOLD_ID not in conf:
        _LOGGER.debug("missing household id in config: %s", conf)
        return False

    # shared data
    hass.data[DOMAIN] = {}
    hass.data[DATA_SURE_PETCARE] = {}
    hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID] = conf[CONF_HOUSEHOLD_ID]
    hass.data[DATA_SURE_PETCARE][SureThingID.FLAP.name] = dict()
    hass.data[DATA_SURE_PETCARE][SureThingID.PET.name] = dict()

    # sure petcare api connection
    hass.data[DATA_SURE_PETCARE][DATA_SUREPY] = SurePetcare(
        conf[CONF_USERNAME], conf[CONF_PASSWORD], conf[CONF_HOUSEHOLD_ID],
        hass.loop, async_get_clientsession(hass), debug=True)

    # add flaps
    hass.data[DATA_SURE_PETCARE][SURE_IDS] = [
        {
            CONF_NAME: flap[CONF_NAME],
            CONF_ID: flap[CONF_ID],
            CONF_TYPE: SureThingID.FLAP.name,
        }
        for flap in conf[CONF_FLAPS]]

    # add pets
    hass.data[DATA_SURE_PETCARE][SURE_IDS].extend([
        {
            CONF_NAME: pet[CONF_NAME],
            CONF_ID: pet[CONF_ID],
            CONF_TYPE: SureThingID.PET.name,
        } for pet in conf[CONF_PETS]])

    # load platforms
    await hass.helpers.discovery.async_load_platform(
        'binary_sensor', DOMAIN, {}, config)
    await hass.helpers.discovery.async_load_platform(
        'sensor', DOMAIN, {}, config)

    return True
