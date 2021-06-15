"""Support for Xiaomi Mi Air Quality Monitor (PM2.5) and Humidifier."""
from dataclasses import dataclass
from enum import Enum
from functools import partial
import logging

from miio import AirHumidifier, AirHumidifierMiot, AirQualityMonitor, DeviceException
from miio.gateway.gateway import (
    GATEWAY_MODEL_AC_V1,
    GATEWAY_MODEL_AC_V2,
    GATEWAY_MODEL_AC_V3,
    GATEWAY_MODEL_EU,
    GatewayException,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
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

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    DOMAIN,
    KEY_COORDINATOR,
    MODELS_HUMIDIFIER_MIOT,
)
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
ATTR_WATER_LEVEL = "water_level"
ATTR_HUMIDITY = "humidity"

SUCCESS = ["ok"]

CONF_MODEL = "model"


@dataclass
class SensorType:
    """Class that holds device specific info for a xiaomi aqara or humidifier sensor."""

    unit: str = None
    icon: str = None
    device_class: str = None
    state_class: str = None


GATEWAY_SENSOR_TYPES = {
    "temperature": SensorType(
        unit=TEMP_CELSIUS,
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "humidity": SensorType(
        unit=PERCENTAGE,
        icon=None,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "pressure": SensorType(
        unit=PRESSURE_HPA,
        icon=None,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "load_power": SensorType(
        unit=POWER_WATT, icon=None, device_class=DEVICE_CLASS_POWER
    ),
}

HUMIDIFIER_SENSOR_TYPES = {
    "temperature": SensorType(
        unit=TEMP_CELSIUS,
        icon=None,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "humidity": SensorType(
        unit=PERCENTAGE,
        icon="mdi:water-percent",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "water_level": SensorType(
        unit=PERCENTAGE,
        icon="mdi:water-check",
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
}

HUMIDIFIER_ATTRIBUTES = {
    ATTR_HUMIDITY: "humidity",
    ATTR_TEMPERATURE: "temperature",
}

HUMIDIFIER_ATTRIBUTES_MIOT = {
    ATTR_HUMIDITY: "humidity",
    ATTR_TEMPERATURE: "temperature",
    ATTR_WATER_LEVEL: "water_level",
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

    model = config_entry.data[CONF_MODEL]
    device = None

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
    elif config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        if model in MODELS_HUMIDIFIER_MIOT:
            device = AirHumidifierMiot(host, token)
            attributes = HUMIDIFIER_ATTRIBUTES_MIOT
        elif model.startswith("zhimi.humidifier."):
            device = AirHumidifier(host, token)
            attributes = HUMIDIFIER_ATTRIBUTES
        if device:
            for attribute in attributes:
                entities.append(
                    XiaomiHumidifierSensor(
                        f"{config_entry.title}_{attribute}",
                        device,
                        config_entry,
                        f"{attribute}_{config_entry.unique_id}",
                        attribute,
                    )
                )
        else:
            unique_id = config_entry.unique_id
            name = config_entry.title
            _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

            device = AirQualityMonitor(host, token)
            entities.append(
                XiaomiAirQualityMonitor(name, device, config_entry, unique_id)
            )

    async_add_entities(entities, update_before_add=True)


class XiaomiHumidifierSensor(XiaomiMiioEntity, SensorEntity):
    """Representation of a Xiaomi Humidifier sensor."""

    def __init__(self, name, device, entry, unique_id, attribute):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id)

        self._name = name
        self._icon = HUMIDIFIER_SENSOR_TYPES[attribute].icon
        self._unit_of_measurement = HUMIDIFIER_SENSOR_TYPES[attribute].unit
        self._device_class = HUMIDIFIER_SENSOR_TYPES[attribute].device_class
        self._state_class = HUMIDIFIER_SENSOR_TYPES[attribute].state_class
        self._available = None
        self._state = None
        self._state_attrs = {}
        self._skip_update = False
        self._attribute = attribute

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

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            if self._available:
                _LOGGER.error(mask_error, exc)
                self._available = False

            return False

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = self._extract_value_from_attribute(state, self._attribute)

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)


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
    def state_class(self):
        """Return the state class of this entity."""
        return GATEWAY_SENSOR_TYPES[self._data_key].state_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sub_device.status[self._data_key]


class XiaomiGatewayIlluminanceSensor(SensorEntity):
    """Representation of the gateway device's illuminance sensor."""

    _attr_device_class = DEVICE_CLASS_ILLUMINANCE
    _attr_unit_of_measurement = UNIT_LUMEN

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
