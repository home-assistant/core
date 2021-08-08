"""Support for Xiaomi Mi Air Quality Monitor (PM2.5) and Humidifier."""
from dataclasses import dataclass
from enum import Enum
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
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER_MIOT,
)
from .device import XiaomiCoordinatedMiioEntity, XiaomiMiioEntity
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

ATTR_ACTUAL_SPEED = "actual_speed"
ATTR_CHARGING = "charging"
ATTR_DISPLAY_CLOCK = "display_clock"
ATTR_HUMIDITY = "humidity"
ATTR_MOTOR_SPEED = "motor_speed"
ATTR_NIGHT_MODE = "night_mode"
ATTR_NIGHT_TIME_BEGIN = "night_time_begin"
ATTR_NIGHT_TIME_END = "night_time_end"
ATTR_POWER = "power"
ATTR_SENSOR_STATE = "sensor_state"
ATTR_WATER_LEVEL = "water_level"


@dataclass
class SensorType:
    """Class that holds device specific info for a xiaomi aqara or humidifier sensor."""

    unit: str = None
    icon: str = None
    device_class: str = None
    state_class: str = None
    valid_min_value: float = None
    valid_max_value: float = None


SENSOR_TYPES = {
    "temperature": SensorType(
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "humidity": SensorType(
        unit=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "pressure": SensorType(
        unit=PRESSURE_HPA,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "load_power": SensorType(
        unit=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    "water_level": SensorType(
        unit=PERCENTAGE,
        icon="mdi:water-check",
        state_class=STATE_CLASS_MEASUREMENT,
        valid_min_value=0.0,
        valid_max_value=100.0,
    ),
    "actual_speed": SensorType(
        unit="rpm",
        icon="mdi:fast-forward",
        state_class=STATE_CLASS_MEASUREMENT,
        valid_min_value=200.0,
        valid_max_value=2000.0,
    ),
    "motor_speed": SensorType(
        unit="rpm",
        icon="mdi:fast-forward",
        state_class=STATE_CLASS_MEASUREMENT,
        valid_min_value=200.0,
        valid_max_value=2000.0,
    ),
}

HUMIDIFIER_SENSORS = {
    ATTR_HUMIDITY: "humidity",
    ATTR_TEMPERATURE: "temperature",
}

HUMIDIFIER_CA1_CB1_SENSORS = {
    ATTR_HUMIDITY: "humidity",
    ATTR_TEMPERATURE: "temperature",
    ATTR_MOTOR_SPEED: "motor_speed",
}

HUMIDIFIER_SENSORS_MIOT = {
    ATTR_HUMIDITY: "humidity",
    ATTR_TEMPERATURE: "temperature",
    ATTR_WATER_LEVEL: "water_level",
    ATTR_ACTUAL_SPEED: "actual_speed",
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
            sensor_variables = set(sub_device.status) & set(SENSOR_TYPES)
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
        model = config_entry.data[CONF_MODEL]
        device = None
        sensors = []
        if model in MODELS_HUMIDIFIER_MIOT:
            device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
            sensors = HUMIDIFIER_SENSORS_MIOT
        elif model in (MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1):
            device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
            sensors = HUMIDIFIER_CA1_CB1_SENSORS
        elif model.startswith("zhimi.humidifier."):
            device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
            sensors = HUMIDIFIER_SENSORS
        else:
            unique_id = config_entry.unique_id
            name = config_entry.title
            _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

            device = AirQualityMonitor(host, token)
            entities.append(
                XiaomiAirQualityMonitor(name, device, config_entry, unique_id)
            )
        for sensor in sensors:
            entities.append(
                XiaomiGenericSensor(
                    f"{config_entry.title} {sensor.replace('_', ' ').title()}",
                    device,
                    config_entry,
                    f"{sensor}_{config_entry.unique_id}",
                    sensor,
                    hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                )
            )

    async_add_entities(entities)


class XiaomiGenericSensor(XiaomiCoordinatedMiioEntity, SensorEntity):
    """Representation of a Xiaomi Humidifier sensor."""

    def __init__(self, name, device, entry, unique_id, attribute, coordinator):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._sensor_config = SENSOR_TYPES[attribute]
        self._attr_device_class = self._sensor_config.device_class
        self._attr_state_class = self._sensor_config.state_class
        self._attr_icon = self._sensor_config.icon
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_unit_of_measurement = self._sensor_config.unit
        self._device = device
        self._entry = entry
        self._attribute = attribute
        self._state = None

    @property
    def state(self):
        """Return the state of the device."""
        self._state = self._extract_value_from_attribute(
            self.coordinator.data, self._attribute
        )
        if (
            self._sensor_config.valid_min_value
            and self._state < self._sensor_config.valid_min_value
        ) or (
            self._sensor_config.valid_max_value
            and self._state > self._sensor_config.valid_max_value
        ):
            return None
        return self._state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value


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
        """Return the icon to use in the frontend."""
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
        return SENSOR_TYPES[self._data_key].icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._data_key].unit

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return SENSOR_TYPES[self._data_key].device_class

    @property
    def state_class(self):
        """Return the state class of this entity."""
        return SENSOR_TYPES[self._data_key].state_class

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
