"""Support for Sure Petcare cat/pet flaps."""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_ICON, CONF_ID,
                                 CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_TYPE, CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (CONF_FLAPS, CONF_HOUSEHOLD_ID, CONF_PETS, DATA_SURE_DATA,
                    DATA_SURE_HOUSEHOLD_NAME, DATA_SURE_LISTENER,
                    DATA_SURE_PETCARE, DATA_SUREPY, DEFAULT_SCAN_INTERVAL,
                    DOMAIN, SURE_IDS, TOPIC_UPDATE)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['surepy>=0.1.1']
SCAN_INTERVAL = timedelta(seconds=60)

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
        vol.Optional(CONF_FLAPS): vol.Schema(vol.All(cv.ensure_list, [FLAP_SCHEMA])),
        vol.Optional(CONF_PETS): vol.Schema(vol.All(cv.ensure_list, [PET_SCHEMA])),
        vol.Optional(CONF_DEVICE_CLASS, default="door"): cv.string,
        vol.Optional(CONF_ICON, default="mdi:door"): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Sure Petcare component."""
    from surepy import SurePetcare
    conf = config.get(DOMAIN, dict())

    hass.data[DOMAIN] = {}
    hass.data[DATA_SURE_PETCARE] = {}
    sure_data = hass.data[DATA_SURE_PETCARE]

    sure_entry_data = dict()

    # Store config in hass.data so the config entry can find it
    sure_data[CONF_USERNAME]: str = conf[CONF_USERNAME]
    sure_data[CONF_PASSWORD]: str = conf[CONF_PASSWORD]
    sure_data[CONF_ICON] = conf[CONF_ICON]

    surepy = SurePetcare(conf[CONF_USERNAME], conf[CONF_PASSWORD], conf[CONF_HOUSEHOLD_ID], hass.loop, async_get_clientsession(hass), debug=True)
    hass.data[DATA_SURE_PETCARE][DATA_SUREPY] = surepy

    flaps: list = [{CONF_NAME: flap[CONF_NAME], CONF_ID: flap[CONF_ID], CONF_TYPE: CONF_FLAPS} for flap in conf[CONF_FLAPS]]
    pets: list = [{CONF_NAME: pet[CONF_NAME], CONF_ID: pet[CONF_ID], CONF_TYPE: CONF_PETS} for pet in conf[CONF_PETS]]
    things: list = flaps + pets

    # User has configured household or flaps
    if CONF_HOUSEHOLD_ID not in conf:
        return True

    configured_households = get_configured_households(hass)

    if conf[CONF_HOUSEHOLD_ID] in configured_households:
        _LOGGER.debug("%s already configured in %s", conf[CONF_HOUSEHOLD_ID], configured_households)
        return True

    sure_entry_data[CONF_USERNAME] = conf[CONF_USERNAME]
    sure_entry_data[CONF_PASSWORD] = conf[CONF_PASSWORD]
    sure_entry_data[CONF_HOUSEHOLD_ID] = conf[CONF_HOUSEHOLD_ID]
    sure_entry_data[DATA_SURE_HOUSEHOLD_NAME] = "SyBe"
    sure_entry_data[SURE_IDS] = list(things)
    hass.data[DATA_SURE_PETCARE][SURE_IDS] = list(things)

    # No existing config entry found, try importing it or trigger link
    # config flow if no existing auth. Because we're inside the setup of
    # this component we'll have to use hass.async_add_job to avoid a
    # deadlock: creating a config entry will set up the component but the
    # setup would block till the entry is created!
    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN,
        context=dict(source=config_entries.SOURCE_IMPORT),
        data=sure_entry_data
    ))

    return True


async def async_setup_entry(hass, entry: ConfigEntry):
    """Set up a bridge from a config entry."""
    # household_id = entry.data[CONF_HOUSEHOLD_ID]
    # household_name = entry.data[DATA_SURE_HOUSEHOLD_NAME]
    # hub_mac = "0000D8803970879C"
    # hub_version = "NjEw"

    async def refresh_sensors(event_time):
        """Refresh Sure Petcare data."""
        if hass.data[DATA_SURE_PETCARE][DATA_SUREPY]:
            surepy = hass.data[DATA_SURE_PETCARE][DATA_SUREPY]
        else:
            _LOGGER.debug(f"using new connection -> {hass.data[DATA_SURE_PETCARE]}")
            from surepy import SurePetcare
            surepy = SurePetcare(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], entry.data[CONF_HOUSEHOLD_ID], hass.loop, async_get_clientsession(hass), debug=True)

        if CONF_FLAPS not in hass.data[DATA_SURE_PETCARE]:
            hass.data[DATA_SURE_PETCARE][CONF_FLAPS] = dict()

        if CONF_PETS not in hass.data[DATA_SURE_PETCARE]:
            hass.data[DATA_SURE_PETCARE][CONF_PETS] = dict()

        response = None

        for thing in entry.data[SURE_IDS]:
            sure_id = thing[CONF_ID]
            sure_type = thing[CONF_TYPE]
            if sure_type == CONF_FLAPS:
                # hass.data[DATA_SURE_PETCARE][sure_type][sure_id] = await surepy.get_flap_data(sure_id)
                response = await surepy.get_flap_data(sure_id)
            elif sure_type == CONF_PETS:
                response = await surepy.get_pet_data(sure_id)

            hass.data[DATA_SURE_PETCARE][sure_type][sure_id] = response[DATA_SURE_DATA]

        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DATA_SURE_PETCARE][DATA_SURE_LISTENER] = {}

    hass.data[DATA_SURE_PETCARE][DATA_SURE_LISTENER][
        entry.entry_id] = async_track_time_interval(
            hass, refresh_sensors,
            hass.data[DATA_SURE_PETCARE].get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, 'binary_sensor'))

    return True


@callback
def get_configured_households(hass):
    """Return a set of configured Ambient PWS instances."""
    return set(entry.data[CONF_HOUSEHOLD_ID] for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class SurePetcareConfigFlow(config_entries.ConfigFlow):
    """Handle a Sure Petcare config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # (this is not implemented yet)
    VERSION = 1

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, info):
        """Import a new Sure Petcare entry as a config entry."""
        return self.async_create_entry(
            title='Sure PetCare',
            data=info,
        )
