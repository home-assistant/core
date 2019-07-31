"""Support for Fronius devices."""
import copy
import logging
import voluptuous as vol

from pyfronius import Fronius

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_RESOURCE, CONF_SENSOR_TYPE, CONF_DEVICE,
                                 CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

CONF_SCOPE = 'scope'

TYPE_INVERTER = 'inverter'
TYPE_STORAGE = 'storage'
TYPE_METER = 'meter'
TYPE_POWER_FLOW = 'power_flow'
# Note that calling the system URL just returns all values of all devices
SCOPE_DEVICE = 'device'
SCOPE_SYSTEM = 'system'

DEFAULT_SCOPE = SCOPE_DEVICE
DEFAULT_DEVICE = 0
DEFAULT_INVERTER = 1
DEFAULT_SCAN_INTERVAL = 60

SENSOR_TYPES = [TYPE_INVERTER, TYPE_STORAGE, TYPE_METER, TYPE_POWER_FLOW]
SCOPE_TYPES = [SCOPE_DEVICE, SCOPE_SYSTEM]


def _device_id_validator(config):
    """Ensure that inverters have default id 1 and other devices 0."""
    config = copy.deepcopy(config)
    for cond in config[CONF_MONITORED_CONDITIONS]:
        if CONF_DEVICE not in cond:
            if cond[CONF_SENSOR_TYPE] == TYPE_INVERTER:
                cond[CONF_DEVICE] = DEFAULT_INVERTER
            else:
                cond[CONF_DEVICE] = DEFAULT_DEVICE
    return config


PLATFORM_SCHEMA = vol.Schema(vol.All(PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE):
        cv.url,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(
            cv.ensure_list,
            [{
                vol.Required(CONF_SENSOR_TYPE): vol.In(SENSOR_TYPES),
                vol.Optional(CONF_SCOPE, default=DEFAULT_SCOPE):
                    vol.In(SCOPE_TYPES),
                vol.Optional(CONF_DEVICE):
                    vol.All(vol.Coerce(int), vol.Range(min=0)),
            }]
        ),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
}), _device_id_validator))


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Set up of Fronius platform."""
    session = async_get_clientsession(hass)
    fronius = Fronius(session, config[CONF_RESOURCE])

    scan_interval = config[CONF_SCAN_INTERVAL]
    for condition in config[CONF_MONITORED_CONDITIONS]:

        device = condition[CONF_DEVICE]
        name = "Fronius {} {} {}".format(
            condition[CONF_SENSOR_TYPE].replace('_', ' ').capitalize(),
            device,
            config[CONF_RESOURCE],
        )
        sensor_type = condition[CONF_SENSOR_TYPE]
        scope = condition[CONF_SCOPE]
        if sensor_type == TYPE_INVERTER:
            if scope == SCOPE_SYSTEM:
                sensor_cls = FroniusInverterSystem
            else:
                sensor_cls = FroniusInverterDevice
        elif sensor_type == TYPE_METER:
            if scope == SCOPE_SYSTEM:
                sensor_cls = FroniusMeterSystem
            else:
                sensor_cls = FroniusMeterDevice
        elif sensor_type == TYPE_POWER_FLOW:
            sensor_cls = FroniusPowerFlow
        else:
            sensor_cls = FroniusStorage

        adapter = sensor_cls(fronius, name, device, async_add_entities)

        async def fetch_data(*_):
            return await adapter.async_update()

        await fetch_data()

        async_track_time_interval(
            hass,
            fetch_data,
            timedelta(seconds=scan_interval)
        )


class FroniusAdapter:
    """The Fronius sensor fetching component."""

    def __init__(self, data, name, device, add_entities):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._device = device
        self._attributes = {}

        self.sensors = set()
        self._registered_sensors = set()
        self._add_entities = add_entities

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        """Retrieve and update latest state."""
        values = {}
        try:
            values = await self._update()
        except ConnectionError:
            _LOGGER.error("Failed to update: connection error")
        except ValueError:
            _LOGGER.error("Failed to update: invalid response returned."
                          "Maybe the configured device is not supported")

        if not values:
            return
        attributes = self._attributes
        # Copy data of current fronius device
        for key, entry in values.items():
            # If the data is directly a sensor
            if 'value' in entry:
                attributes[key] = entry
            # Handle system overview with multiple sensors
            elif '1' in entry or '0' in entry:
                for index in values:
                    attributes['{}_{}'.format(
                        key, index
                    )] = values[index]
        self._attributes = attributes

        # Add discovered value fields as sensors
        # because some fields are only sent temporarily
        new_sensors = []
        for key in attributes:
            if key not in self.sensors:
                self.sensors.add(key)
                _LOGGER.info(
                    "Discovered %s, adding as sensor.",
                    key
                )
                new_sensors.append(FroniusTemplateSensor(self, key))
        self._add_entities(new_sensors, True)

        # Schedule an update for all included sensors
        for sensor in self._registered_sensors:
            sensor.async_schedule_update_ha_state(True)

    async def _update(self):
        """Return values of interest."""
        pass

    async def register(self, sensor):
        """Register child sensor for update subscriptions."""
        self._registered_sensors.add(sensor)


class FroniusInverterSystem(FroniusAdapter):
    """Sensor for the fronius inverter with system scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_system_inverter_data()


class FroniusInverterDevice(FroniusAdapter):
    """Sensor for the fronius inverter with device scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_inverter_data(self._device)


class FroniusStorage(FroniusAdapter):
    """Sensor for the fronius battery storage."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_storage_data(self._device)


class FroniusMeterSystem(FroniusAdapter):
    """Sensor for the fronius meter with system scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_system_meter_data()


class FroniusMeterDevice(FroniusAdapter):
    """Sensor for the fronius meter with device scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_meter_data(self._device)


class FroniusPowerFlow(FroniusAdapter):
    """Sensor for the fronius power flow."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_power_flow()


class FroniusTemplateSensor(Entity):
    """Sensor for the single values (e.g. pv power, ac power)."""

    def __init__(self, parent: FroniusAdapter, name):
        """Initialize a singular value sensor."""
        self._name = name
        self.parent = parent
        self._state = None
        self._unit = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(
            self._name.replace('_', ' ').capitalize(),
            self.parent.name
        )

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def should_poll(self):
        return False

    async def async_update(self):
        """Update the internal state."""
        state = self.parent.device_state_attributes.get(self._name)
        self._state = state.get('value')
        self._unit = state.get('unit')

    async def async_added_to_hass(self):
        """Register at parent component for updates."""
        await self.parent.register(self)

    def __hash__(self):
        """Hash sensor by hashing its name."""
        return hash(self.name)

