"""Support for the Awair indoor air quality monitor."""

from datetime import timedelta
import logging
import math

from python_awair import AwairClient
import voluptuous as vol

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_ACCESS_TOKEN,
    CONF_DEVICES,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

ATTR_SCORE = "score"
ATTR_TIMESTAMP = "timestamp"
ATTR_LAST_API_UPDATE = "last_api_update"
ATTR_COMPONENT = "component"
ATTR_VALUE = "value"
ATTR_SENSORS = "sensors"

CONF_UUID = "uuid"

DEVICE_CLASS_PM2_5 = "PM2.5"
DEVICE_CLASS_PM10 = "PM10"
DEVICE_CLASS_CARBON_DIOXIDE = "CO2"
DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS = "VOC"
DEVICE_CLASS_SCORE = "score"

SENSOR_TYPES = {
    "TEMP": {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "unit_of_measurement": TEMP_CELSIUS,
        "icon": "mdi:thermometer",
    },
    "HUMID": {
        "device_class": DEVICE_CLASS_HUMIDITY,
        "unit_of_measurement": UNIT_PERCENTAGE,
        "icon": "mdi:water-percent",
    },
    "CO2": {
        "device_class": DEVICE_CLASS_CARBON_DIOXIDE,
        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
        "icon": "mdi:periodic-table-co2",
    },
    "VOC": {
        "device_class": DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        "unit_of_measurement": CONCENTRATION_PARTS_PER_BILLION,
        "icon": "mdi:cloud",
    },
    # Awair docs don't actually specify the size they measure for 'dust',
    # but 2.5 allows the sensor to show up in HomeKit
    "DUST": {
        "device_class": DEVICE_CLASS_PM2_5,
        "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "icon": "mdi:cloud",
    },
    "PM25": {
        "device_class": DEVICE_CLASS_PM2_5,
        "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "icon": "mdi:cloud",
    },
    "PM10": {
        "device_class": DEVICE_CLASS_PM10,
        "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "icon": "mdi:cloud",
    },
    "score": {
        "device_class": DEVICE_CLASS_SCORE,
        "unit_of_measurement": UNIT_PERCENTAGE,
        "icon": "mdi:percent",
    },
}

AWAIR_QUOTA = 300

# This is the minimum time between throttled update calls.
# Don't bother asking us for state more often than that.
SCAN_INTERVAL = timedelta(minutes=5)

AWAIR_DEVICE_SCHEMA = vol.Schema({vol.Required(CONF_UUID): cv.string})

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [AWAIR_DEVICE_SCHEMA]),
    }
)


# Awair *heavily* throttles calls that get user information,
# and calls that get the list of user-owned devices - they
# allow 30 per DAY. So, we permit a user to provide a static
# list of devices, and they may provide the same set of information
# that the devices() call would return. However, the only thing
# used at this time is the `uuid` value.
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Connect to the Awair API and find devices."""

    token = config[CONF_ACCESS_TOKEN]
    client = AwairClient(token, session=async_get_clientsession(hass))

    try:
        all_devices = []
        devices = config.get(CONF_DEVICES, await client.devices())

        # Try to throttle dynamically based on quota and number of devices.
        throttle_minutes = math.ceil(60 / ((AWAIR_QUOTA / len(devices)) / 24))
        throttle = timedelta(minutes=throttle_minutes)

        for device in devices:
            _LOGGER.debug("Found awair device: %s", device)
            awair_data = AwairData(client, device[CONF_UUID], throttle)
            await awair_data.async_update()
            for sensor in SENSOR_TYPES:
                if sensor in awair_data.data:
                    awair_sensor = AwairSensor(awair_data, device, sensor, throttle)
                    all_devices.append(awair_sensor)

        async_add_entities(all_devices, True)
        return
    except AwairClient.AuthError:
        _LOGGER.error("Awair API access_token invalid")
    except AwairClient.RatelimitError:
        _LOGGER.error("Awair API ratelimit exceeded.")
    except (
        AwairClient.QueryError,
        AwairClient.NotFoundError,
        AwairClient.GenericError,
    ) as error:
        _LOGGER.error("Unexpected Awair API error: %s", error)

    raise PlatformNotReady


class AwairSensor(Entity):
    """Implementation of an Awair device."""

    def __init__(self, data, device, sensor_type, throttle):
        """Initialize the sensor."""
        self._uuid = device[CONF_UUID]
        self._device_class = SENSOR_TYPES[sensor_type]["device_class"]
        self._name = f"Awair {self._device_class}"
        unit = SENSOR_TYPES[sensor_type]["unit_of_measurement"]
        self._unit_of_measurement = unit
        self._data = data
        self._type = sensor_type
        self._throttle = throttle

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self._type]["icon"]

    @property
    def state(self):
        """Return the state of the device."""
        return self._data.data[self._type]

    @property
    def device_state_attributes(self):
        """Return additional attributes."""
        return self._data.attrs

    # The Awair device should be reporting metrics in quite regularly.
    # Based on the raw data from the API, it looks like every ~10 seconds
    # is normal. Here we assert that the device is not available if the
    # last known API timestamp is more than (3 * throttle) minutes in the
    # past. It implies that either hass is somehow unable to query the API
    # for new data or that the device is not checking in. Either condition
    # fits the definition for 'not available'. We pick (3 * throttle) minutes
    # to allow for transient errors to correct themselves.
    @property
    def available(self):
        """Device availability based on the last update timestamp."""
        if ATTR_LAST_API_UPDATE not in self.device_state_attributes:
            return False

        last_api_data = self.device_state_attributes[ATTR_LAST_API_UPDATE]
        return (dt.utcnow() - last_api_data) < (3 * self._throttle)

    @property
    def unique_id(self):
        """Return the unique id of this entity."""
        return f"{self._uuid}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data."""
        await self._data.async_update()


class AwairData:
    """Get data from Awair API."""

    def __init__(self, client, uuid, throttle):
        """Initialize the data object."""
        self._client = client
        self._uuid = uuid
        self.data = {}
        self.attrs = {}
        self.async_update = Throttle(throttle)(self._async_update)

    async def _async_update(self):
        """Get the data from Awair API."""
        resp = await self._client.air_data_latest(self._uuid)

        if not resp:
            return

        timestamp = dt.parse_datetime(resp[0][ATTR_TIMESTAMP])
        self.attrs[ATTR_LAST_API_UPDATE] = timestamp
        self.data[ATTR_SCORE] = resp[0][ATTR_SCORE]

        # The air_data_latest call only returns one item, so this should
        # be safe to only process one entry.
        for sensor in resp[0][ATTR_SENSORS]:
            self.data[sensor[ATTR_COMPONENT]] = round(sensor[ATTR_VALUE], 1)

        _LOGGER.debug("Got Awair Data for %s: %s", self._uuid, self.data)
