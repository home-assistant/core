"""Support for Sure Petcare cat/pet flaps."""
import logging

from surepy import (
    SurePetcare,
    SurePetcareAuthenticationError,
    SurePetcareError,
    SureThingID,
)
import voluptuous as vol

from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_FLAPS,
    CONF_HOUSEHOLD_ID,
    CONF_PETS,
    DATA_SURE_PETCARE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SPC,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


FLAP_SCHEMA = vol.Schema(
    {vol.Required(CONF_ID): cv.positive_int, vol.Required(CONF_NAME): cv.string}
)

PET_SCHEMA = vol.Schema(
    {vol.Required(CONF_ID): cv.positive_int, vol.Required(CONF_NAME): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_HOUSEHOLD_ID): cv.positive_int,
                vol.Required(CONF_FLAPS): vol.All(cv.ensure_list, [FLAP_SCHEMA]),
                vol.Required(CONF_PETS): vol.All(cv.ensure_list, [PET_SCHEMA]),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize the Sure Petcare component."""
    conf = config[DOMAIN]

    # update interval
    scan_interval = conf[CONF_SCAN_INTERVAL]

    # shared data
    hass.data[DOMAIN] = hass.data[DATA_SURE_PETCARE] = {}

    # sure petcare api connection
    try:
        surepy = SurePetcare(
            conf[CONF_USERNAME],
            conf[CONF_PASSWORD],
            conf[CONF_HOUSEHOLD_ID],
            hass.loop,
            async_get_clientsession(hass),
        )
        await surepy.refresh_token()
    except SurePetcareAuthenticationError:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        return False
    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong %s!", error)
        return False

    # add flaps
    things = [
        {
            CONF_NAME: flap[CONF_NAME],
            CONF_ID: flap[CONF_ID],
            CONF_TYPE: SureThingID.FLAP.name,
        }
        for flap in conf[CONF_FLAPS]
    ]

    # add pets
    things.extend(
        [
            {
                CONF_NAME: pet[CONF_NAME],
                CONF_ID: pet[CONF_ID],
                CONF_TYPE: SureThingID.PET.name,
            }
            for pet in conf[CONF_PETS]
        ]
    )

    spc = hass.data[DATA_SURE_PETCARE][SPC] = SurePetcareAPI(
        hass, surepy, things, conf[CONF_HOUSEHOLD_ID]
    )

    # initial update
    await spc.async_update()

    async_track_time_interval(hass, spc.async_update, scan_interval)

    # load platforms
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("binary_sensor", DOMAIN, {}, config)
    )
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )

    return True


class SurePetcareAPI:
    """Define a generic Sure Petcare object."""

    def __init__(self, hass, surepy, ids, household_id):
        """Initialize the Sure Petcare object."""
        self.hass = hass
        self.surepy = surepy
        self.household_id = household_id
        self.ids = ids
        self.states = {}

    async def async_update(self, args=None):
        """Refresh Sure Petcare data."""
        for thing in self.ids:
            sure_id = thing[CONF_ID]
            sure_type = thing[CONF_TYPE]

            try:
                type_state = self.states.setdefault(sure_type, {})

                if sure_type == SureThingID.FLAP.name:
                    type_state[sure_id] = await self.surepy.get_flap_data(sure_id)
                elif sure_type == SureThingID.PET.name:
                    type_state[sure_id] = await self.surepy.get_pet_data(sure_id)

            except SurePetcareError as error:
                _LOGGER.error("Unable to retrieve data from surepetcare.io: %s", error)

        async_dispatcher_send(self.hass, TOPIC_UPDATE)
