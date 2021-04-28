"""Support for Xiaomi Mi Air Quality Monitor (PM2.5)."""
from dataclasses import dataclass
import logging

from miio import AirQualityMonitor, DeviceException
from miio.gateway.gateway import (
    GATEWAY_MODEL_AC_V1,
    GATEWAY_MODEL_AC_V2,
    GATEWAY_MODEL_AC_V3,
    GATEWAY_MODEL_EU,
    GatewayException,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

from .const import CONF_DEVICE, CONF_FLOW_TYPE, CONF_GATEWAY, DOMAIN, KEY_COORDINATOR
from .device import XiaomiMiioEntity
from .gateway import XiaomiGatewayDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Sensor"
UNIT_LUMEN = "lm"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

ATTR_POWER = "power"
ATTR_CHARGING = "charging"
ATTR_DISPLAY_CLOCK = "display_clock"
ATTR_NIGHT_MODE = "night_mode"
ATTR_NIGHT_TIME_BEGIN = "night_time_begin"
ATTR_NIGHT_TIME_END = "night_time_end"
ATTR_SENSOR_STATE = "sensor_state"

SUCCESS = ["ok"]


@dataclass
class SensorType:
    """Class that holds device specific info for a xiaomi aqara sensor."""

    unit: str = None
    icon: str = None
    device_class: str = None


GATEWAY_SENSOR_TYPES = {
    "temperature": SensorType(
        unit=TEMP_CELSIUS, icon=None, device_class=DEVICE_CLASS_TEMPERATURE
    ),
    "humidity": SensorType(
        unit=PERCENTAGE, icon=None, device_class=DEVICE_CLASS_HUMIDITY
    ),
    "pressure": SensorType(
        unit=PRESSURE_HPA, icon=None, device_class=DEVICE_CLASS_PRESSURE
    ),
    "load_power": SensorType(
        unit=POWER_WATT, icon=None, device_class=DEVICE_CLASS_POWER
    ),
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Miio configuration from YAML."""
    _LOGGER.warning(
        "Loading Xiaomi Miio Sensor via platform setup is deprecated. "
        "Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi sensor from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        gateway = hass.data[DOMAIN][config_entry.entry_id][CONF_GATEWAY]
        # Gateway illuminance sensor
        if gateway.model not in [
            GATEWAY_MODEL_AC_V1,
            GATEWAY_MODEL_AC_V2,
            GATEWAY_MODEL_AC_V3,
            GATEWAY_MODEL_EU,
        ]:
            entities.append(
                XiaomiGatewayIlluminanceSensor(
                    gateway, config_entry.title, config_entry.unique_id
                )
            )
        # Gateway sub devices
        sub_devices = gateway.devices
        coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
        for sub_device in sub_devices.values():
            sensor_variables = set(sub_device.status) & set(GATEWAY_SENSOR_TYPES)
            if sensor_variables:
                entities.extend(
                    [
                        XiaomiGatewaySensor(
                            coordinator, sub_device, config_entry, variable
                        )
                        for variable in sensor_variables
                    ]
                )

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        name = config_entry.title
        unique_id = config_entry.unique_id

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        device = AirQualityMonitor(host, token)
        entities.append(XiaomiAirQualityMonitor(name, device, config_entry, unique_id))

    async_add_entities(entities, update_before_add=True)


class XiaomiAirQualityMonitor(XiaomiMiioEntity, SensorEntity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id)

        self._icon = "mdi:cloud"
        self._unit_of_measurement = "AQI"
        self._available = None
        self._state = None
        self._state_attrs = {
            ATTR_POWER: None,
            ATTR_BATTERY_LEVEL: None,
            ATTR_CHARGING: None,
            ATTR_DISPLAY_CLOCK: None,
            ATTR_NIGHT_MODE: None,
            ATTR_NIGHT_TIME_BEGIN: None,
            ATTR_NIGHT_TIME_END: None,
            ATTR_SENSOR_STATE: None,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_update(self):
        """Fetch state from the miio device."""
        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.aqi
            self._state_attrs.update(
                {
                    ATTR_POWER: state.power,
                    ATTR_CHARGING: state.usb_power,
                    ATTR_BATTERY_LEVEL: state.battery,
                    ATTR_DISPLAY_CLOCK: state.display_clock,
                    ATTR_NIGHT_MODE: state.night_mode,
                    ATTR_NIGHT_TIME_BEGIN: state.night_time_begin,
                    ATTR_NIGHT_TIME_END: state.night_time_end,
                    ATTR_SENSOR_STATE: state.sensor_state,
                }
            )

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)


class XiaomiGatewaySensor(XiaomiGatewayDevice, SensorEntity):
    """Representation of a XiaomiGatewaySensor."""

    def __init__(self, coordinator, sub_device, entry, data_key):
        """Initialize the XiaomiSensor."""
        super().__init__(coordinator, sub_device, entry)
        self._data_key = data_key
        self._unique_id = f"{sub_device.sid}-{data_key}"
        self._name = f"{data_key} ({sub_device.sid})".capitalize()

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return GATEWAY_SENSOR_TYPES[self._data_key].icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return GATEWAY_SENSOR_TYPES[self._data_key].unit

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return GATEWAY_SENSOR_TYPES[self._data_key].device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sub_device.status[self._data_key]


class XiaomiGatewayIlluminanceSensor(SensorEntity):
    """Representation of the gateway device's illuminance sensor."""

    def __init__(self, gateway_device, gateway_name, gateway_device_id):
        """Initialize the entity."""
        self._gateway = gateway_device
        self._name = f"{gateway_name} Illuminance"
        self._gateway_device_id = gateway_device_id
        self._unique_id = f"{gateway_device_id}-illuminance"
        self._available = False
        self._state = None

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info of the gateway."""
        return {"identifiers": {(DOMAIN, self._gateway_device_id)}}

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return UNIT_LUMEN

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_ILLUMINANCE

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_update(self):
        """Fetch state from the device."""
        try:
            self._state = await self.hass.async_add_executor_job(
                self._gateway.get_illumination
            )
            self._available = True
        except GatewayException as ex:
            if self._available:
                self._available = False
                _LOGGER.error(
                    "Got exception while fetching the gateway illuminance state: %s", ex
                )
