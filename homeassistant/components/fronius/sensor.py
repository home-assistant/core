"""Support for Fronius devices."""
import copy
import logging
import voluptuous as vol

from pyfronius import Fronius

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_RESOURCE,
    CONF_SENSOR_TYPE,
    CONF_DEVICE,
    CONF_MONITORED_CONDITIONS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_SCOPE = "scope"

TYPE_INVERTER = "inverter"
TYPE_STORAGE = "storage"
TYPE_METER = "meter"
TYPE_POWER_FLOW = "power_flow"
SCOPE_DEVICE = "device"
SCOPE_SYSTEM = "system"

DEFAULT_SCOPE = SCOPE_DEVICE
DEFAULT_DEVICE = 0
DEFAULT_INVERTER = 1

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


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_RESOURCE): cv.url,
                vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
                    cv.ensure_list,
                    [
                        {
                            vol.Required(CONF_SENSOR_TYPE): vol.In(SENSOR_TYPES),
                            vol.Optional(CONF_SCOPE, default=DEFAULT_SCOPE): vol.In(
                                SCOPE_TYPES
                            ),
                            vol.Optional(CONF_DEVICE): vol.All(
                                vol.Coerce(int), vol.Range(min=0)
                            ),
                        }
                    ],
                ),
            }
        ),
        _device_id_validator,
    )
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up of Fronius platform."""
    session = async_get_clientsession(hass)
    fronius = Fronius(session, config[CONF_RESOURCE])

    sensors = []
    for condition in config[CONF_MONITORED_CONDITIONS]:

        device = condition[CONF_DEVICE]
        name = "Fronius {} {} {}".format(
            condition[CONF_SENSOR_TYPE].replace("_", " ").capitalize(),
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

        sensors.append(sensor_cls(fronius, name, device))

    async_add_entities(sensors, True)


class FroniusSensor(Entity):
    """The Fronius sensor implementation."""

    def __init__(self, data, name, device):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._device = device
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current state."""
        return self._state

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
            _LOGGER.error(
                "Failed to update: invalid response returned."
                "Maybe the configured device is not supported"
            )

        if values:
            self._state = values["status"]["Code"]
            attributes = {}
            for key in values:
                if "value" in values[key]:
                    attributes[key] = values[key].get("value", 0)
            self._attributes = attributes

    async def _update(self):
        """Return values of interest."""
        pass


class FroniusInverterSystem(FroniusSensor):
    """Sensor for the fronius inverter with system scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_system_inverter_data()


class FroniusInverterDevice(FroniusSensor):
    """Sensor for the fronius inverter with device scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_inverter_data(self._device)


class FroniusStorage(FroniusSensor):
    """Sensor for the fronius battery storage."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_storage_data(self._device)


class FroniusMeterSystem(FroniusSensor):
    """Sensor for the fronius meter with system scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_system_meter_data()


class FroniusMeterDevice(FroniusSensor):
    """Sensor for the fronius meter with device scope."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_meter_data(self._device)


class FroniusPowerFlow(FroniusSensor):
    """Sensor for the fronius power flow."""

    async def _update(self):
        """Get the values for the current state."""
        return await self.data.current_power_flow()
