"""Support for Sure Petcare cat/pet flaps."""
import logging

import voluptuous as vol
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_ICON, CONF_ID,
                                 CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_TYPE, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (CONF_FLAPS, CONF_HOUSEHOLD_ID, CONF_PETS,
                    DATA_SURE_PETCARE, DATA_SUREPY, DEFAULT_SCAN_INTERVAL,
                    DOMAIN, SURE_IDS, TOPIC_UPDATE, SureThingID)

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
        vol.Required(CONF_FLAPS): vol.Schema(
            vol.All(cv.ensure_list, [FLAP_SCHEMA])),
        vol.Required(CONF_PETS): vol.Schema(
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

    # shared data
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_SCAN_INTERVAL] = conf[CONF_SCAN_INTERVAL]
    hass.data[DATA_SURE_PETCARE] = {}
    hass.data[DATA_SURE_PETCARE][CONF_USERNAME] = CONF_USERNAME
    hass.data[DATA_SURE_PETCARE][CONF_PASSWORD] = CONF_PASSWORD
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

    spc_api = SurePetcareAPI(hass)

    async_track_time_interval(hass, spc_api.async_update, SCAN_INTERVAL)

    # load platforms
    await hass.helpers.discovery.async_load_platform(
        'binary_sensor', DOMAIN, {}, config)
    await hass.helpers.discovery.async_load_platform(
        'sensor', DOMAIN, {}, config)

    return True


class SurePetcareAPI:
    """Define a generic Sure Petcare object."""

    def __init__(self, hass):
        """Initialize the Sure Petcare object."""
        self._hass = hass

    async def async_update(self, args):
        """Refresh Sure Petcare data."""
        from surepy import SurePetcareError

        if self._hass.data[DATA_SURE_PETCARE][DATA_SUREPY]:
            surepy = self._hass.data[DATA_SURE_PETCARE][DATA_SUREPY]
        else:
            from surepy import SurePetcare
            surepy = SurePetcare(
                self._hass.data[DATA_SURE_PETCARE][CONF_USERNAME],
                self._hass.data[DATA_SURE_PETCARE][CONF_PASSWORD],
                self._hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID],
                self._hass.loop, async_get_clientsession(self._hass),
                debug=True)

        if SureThingID.FLAP.name not in self._hass.data[DATA_SURE_PETCARE]:
            self._hass.data[DATA_SURE_PETCARE][SureThingID.FLAP.name] = dict()

        if SureThingID.PET.name not in self._hass.data[DATA_SURE_PETCARE]:
            self._hass.data[DATA_SURE_PETCARE][SureThingID.PET.name] = dict()

        for thing in self._hass.data[DATA_SURE_PETCARE][SURE_IDS]:
            sure_id = thing[CONF_ID]
            sure_type = thing[CONF_TYPE]

            try:
                if sure_type == SureThingID.FLAP.name:
                    self._hass.data[DATA_SURE_PETCARE][sure_type][
                        sure_id] = await surepy.get_flap_data(sure_id)
                elif sure_type == SureThingID.PET.name:
                    self._hass.data[DATA_SURE_PETCARE][sure_type][
                        sure_id] = await surepy.get_pet_data(sure_id)
            except SurePetcareError as error:
                _LOGGER.debug(
                    "Unable to retrieve data from surepetcare.io: %s", error)

        async_dispatcher_send(self._hass, TOPIC_UPDATE)
