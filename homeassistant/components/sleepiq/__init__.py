"""Support for SleepIQ from SleepNumber."""
from datetime import timedelta
import logging

from sleepyq import Sleepyq
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    ATTR_ENTITY,
    ATTR_SLEEP_NUMBER,
    DOMAIN,
    SERVICE_SET_SLEEP_NUMBER,
    SLEEP_NUMBER,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_SLEEP_NUMBER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY): cv.entity_ids,
        vol.Optional(ATTR_SLEEP_NUMBER, default=100): vol.Range(0, 100),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the SleepIQ component.

    Will automatically load sensor components to support
    devices discovered on the account.
    """
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    client = Sleepyq(username, password)
    try:
        data = SleepIQData(client)
        data.update()
    except ValueError:
        message = """
            SleepIQ failed to login, double check your username and password"
        """
        _LOGGER.error(message)
        return False

    hass.data[DOMAIN] = data
    discovery.load_platform(hass, "sensor", DOMAIN, {}, config)
    discovery.load_platform(hass, "binary_sensor", DOMAIN, {}, config)

    def handle_set_sleep_number(call):
        SleepIQService.set_sleepnumber(call, hass, client)

    hass.services.register(
        DOMAIN,
        SERVICE_SET_SLEEP_NUMBER,
        handle_set_sleep_number,
        schema=SERVICE_SET_SLEEP_NUMBER_SCHEMA,
    )

    return True


class SleepIQData:
    """Get the latest data from SleepIQ."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client
        self.beds = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from SleepIQ."""
        self._client.login()
        beds = self._client.beds_with_sleeper_status()

        self.beds = {bed.bed_id: bed for bed in beds}


class SleepIQSensor(Entity):
    """Implementation of a SleepIQ sensor."""

    def __init__(self, sleepiq_data, bed_id, side):
        """Initialize the sensor."""
        self._bed_id = bed_id
        self._side = side
        self.sleepiq_data = sleepiq_data
        self.side = None
        self.bed = None

        # added by subclass
        self._name = None
        self.type = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "SleepNumber {} {} {}".format(
            self.bed.name, self.side.sleeper.first_name, self._name
        )

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        # Call the API for new sleepiq data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits.
        self.sleepiq_data.update()

        self.bed = self.sleepiq_data.beds[self._bed_id]
        self.side = getattr(self.bed, self._side)


class SleepIQService:
    """SleepIQ Services."""

    @staticmethod
    def set_sleepnumber(call, hass, client):
        """Call sleepyq library to set the Sleep Number setting of a side of a bed."""
        entity_ids = call.data.get("entity_id", {})
        new_value = call.data.get(SLEEP_NUMBER, 100)

        for entity_id in entity_ids:
            entity = hass.states.get(entity_id)
            if entity is not None:
                bed_id = entity.attributes.get("bed_id")
                side = entity.attributes.get("side")
                if bed_id is not None and side is not None:
                    try:
                        client.set_sleepnumber(side, new_value, bed_id)
                    except ValueError:
                        message = """
                            SleepIQ failed to set the sleep number, check your username and password"
                        """
                        _LOGGER.error(message)
                else:
                    _LOGGER.error(
                        "BedID and/or Side missing from EntityID %s. BedID: %s; Side: %s",
                        entity_id,
                        bed_id,
                        side,
                    )
            else:
                _LOGGER.error("EntityID %s does not exist", entity_id)
                return False

        return True
