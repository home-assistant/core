"""Support for Xiaomi Mi Air Quality Monitor (PM2.5) and Humidifier."""
from __future__ import annotations

from dataclasses import dataclass
import datetime
from enum import Enum
import logging

from miio import AirQualityMonitor, DeviceException
from miio.gateway.gateway import (
    GATEWAY_MODEL_AC_V1,
    GATEWAY_MODEL_AC_V2,
    GATEWAY_MODEL_AC_V3,
    GATEWAY_MODEL_AQARA,
    GATEWAY_MODEL_EU,
    GatewayException,
)

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    AREA_SQUARE_METERS,
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_HOST,
    CONF_TOKEN,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    TIME_HOURS,
    TIME_SECONDS,
    VOLUME_CUBIC_METERS,
)

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    KEY_VACUUM_CLEAN_HISTORY_STATUS,
    KEY_VACUUM_CONSUMABLE_STATUS,
    KEY_VACUUM_DND_STATUS,
    KEY_VACUUM_LAST_CLEAN_STATUS,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CB1,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V2,
    MODEL_AIRPURIFIER_V3,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
    MODELS_PURIFIER_MIIO,
    MODELS_PURIFIER_MIOT,
    MODELS_VACUUM,
)
from .device import XiaomiCoordinatedMiioEntity, XiaomiMiioEntity
from .gateway import XiaomiGatewayDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Sensor"
UNIT_LUMEN = "lm"

ATTR_ACTUAL_SPEED = "actual_speed"
ATTR_AIR_QUALITY = "air_quality"
ATTR_AQI = "aqi"
ATTR_CARBON_DIOXIDE = "co2"
ATTR_CHARGING = "charging"
ATTR_DISPLAY_CLOCK = "display_clock"
ATTR_FILTER_LIFE_REMAINING = "filter_life_remaining"
ATTR_FILTER_HOURS_USED = "filter_hours_used"
ATTR_FILTER_USE = "filter_use"
ATTR_HUMIDITY = "humidity"
ATTR_ILLUMINANCE = "illuminance"
ATTR_ILLUMINANCE_LUX = "illuminance_lux"
ATTR_LOAD_POWER = "load_power"
ATTR_MOTOR2_SPEED = "motor2_speed"
ATTR_MOTOR_SPEED = "motor_speed"
ATTR_NIGHT_MODE = "night_mode"
ATTR_NIGHT_TIME_BEGIN = "night_time_begin"
ATTR_NIGHT_TIME_END = "night_time_end"
ATTR_PM25 = "pm25"
ATTR_POWER = "power"
ATTR_PRESSURE = "pressure"
ATTR_PURIFY_VOLUME = "purify_volume"
ATTR_SENSOR_STATE = "sensor_state"
ATTR_WATER_LEVEL = "water_level"
ATTR_DND_START = "start"
ATTR_DND_END = "end"
ATTR_LAST_CLEAN_TIME = "duration"
ATTR_LAST_CLEAN_AREA = "area"
ATTR_LAST_CLEAN_START = "start"
ATTR_LAST_CLEAN_END = "end"
ATTR_CLEAN_HISTORY_TOTAL_DURATION = "total_duration"
ATTR_CLEAN_HISTORY_TOTAL_AREA = "total_area"
ATTR_CLEAN_HISTORY_COUNT = "count"
ATTR_CLEAN_HISTORY_DUST_COLLECTION_COUNT = "dust_collection_count"
ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT = "main_brush_left"
ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT = "side_brush_left"
ATTR_CONSUMABLE_STATUS_FILTER_LEFT = "filter_left"
ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT = "sensor_dirty_left"


@dataclass
class XiaomiMiioSensorDescription(SensorEntityDescription):
    """Class that holds device specific info for a xiaomi aqara or humidifier sensor."""

    attributes: tuple = ()
    parent_key: str | None = None


SENSOR_TYPES = {
    ATTR_TEMPERATURE: XiaomiMiioSensorDescription(
        key=ATTR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_HUMIDITY: XiaomiMiioSensorDescription(
        key=ATTR_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_PRESSURE: XiaomiMiioSensorDescription(
        key=ATTR_PRESSURE,
        name="Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_LOAD_POWER: XiaomiMiioSensorDescription(
        key=ATTR_LOAD_POWER,
        name="Load Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    ATTR_WATER_LEVEL: XiaomiMiioSensorDescription(
        key=ATTR_WATER_LEVEL,
        name="Water Level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-check",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_ACTUAL_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_ACTUAL_SPEED,
        name="Actual Speed",
        native_unit_of_measurement="rpm",
        icon="mdi:fast-forward",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_MOTOR_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_MOTOR_SPEED,
        name="Motor Speed",
        native_unit_of_measurement="rpm",
        icon="mdi:fast-forward",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_MOTOR2_SPEED: XiaomiMiioSensorDescription(
        key=ATTR_MOTOR2_SPEED,
        name="Second Motor Speed",
        native_unit_of_measurement="rpm",
        icon="mdi:fast-forward",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_ILLUMINANCE: XiaomiMiioSensorDescription(
        key=ATTR_ILLUMINANCE,
        name="Illuminance",
        native_unit_of_measurement=UNIT_LUMEN,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_ILLUMINANCE_LUX: XiaomiMiioSensorDescription(
        key=ATTR_ILLUMINANCE,
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_AIR_QUALITY: XiaomiMiioSensorDescription(
        key=ATTR_AIR_QUALITY,
        native_unit_of_measurement="AQI",
        icon="mdi:cloud",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_PM25: XiaomiMiioSensorDescription(
        key=ATTR_AQI,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:blur",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_FILTER_LIFE_REMAINING: XiaomiMiioSensorDescription(
        key=ATTR_FILTER_LIFE_REMAINING,
        name="Filter Life Remaining",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:air-filter",
        state_class=STATE_CLASS_MEASUREMENT,
        attributes=("filter_type",),
    ),
    ATTR_FILTER_USE: XiaomiMiioSensorDescription(
        key=ATTR_FILTER_HOURS_USED,
        name="Filter Use",
        native_unit_of_measurement=TIME_HOURS,
        icon="mdi:clock-outline",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_CARBON_DIOXIDE: XiaomiMiioSensorDescription(
        key=ATTR_CARBON_DIOXIDE,
        name="Carbon Dioxide",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    ATTR_PURIFY_VOLUME: XiaomiMiioSensorDescription(
        key=ATTR_PURIFY_VOLUME,
        name="Purify Volume",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
}

HUMIDIFIER_MIIO_SENSORS = (ATTR_HUMIDITY, ATTR_TEMPERATURE, ATTR_WATER_LEVEL)
HUMIDIFIER_CA1_CB1_SENSORS = (
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
    ATTR_MOTOR_SPEED,
    ATTR_WATER_LEVEL,
)
HUMIDIFIER_MIOT_SENSORS = (
    ATTR_ACTUAL_SPEED,
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
    ATTR_WATER_LEVEL,
)
HUMIDIFIER_MJJSQ_SENSORS = (ATTR_HUMIDITY, ATTR_TEMPERATURE)

PURIFIER_MIIO_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TEMPERATURE,
)
PURIFIER_MIOT_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
)
PURIFIER_V2_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
)
PURIFIER_V3_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_ILLUMINANCE_LUX,
    ATTR_MOTOR2_SPEED,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
)
PURIFIER_PRO_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_ILLUMINANCE_LUX,
    ATTR_MOTOR2_SPEED,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_PURIFY_VOLUME,
    ATTR_TEMPERATURE,
)
PURIFIER_PRO_V7_SENSORS = (
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_ILLUMINANCE_LUX,
    ATTR_MOTOR2_SPEED,
    ATTR_MOTOR_SPEED,
    ATTR_PM25,
    ATTR_TEMPERATURE,
)
AIRFRESH_SENSORS = (
    ATTR_CARBON_DIOXIDE,
    ATTR_FILTER_LIFE_REMAINING,
    ATTR_FILTER_USE,
    ATTR_HUMIDITY,
    ATTR_ILLUMINANCE_LUX,
    ATTR_PM25,
    ATTR_TEMPERATURE,
)

MODEL_TO_SENSORS_MAP = {
    MODEL_AIRHUMIDIFIER_CA1: HUMIDIFIER_CA1_CB1_SENSORS,
    MODEL_AIRHUMIDIFIER_CB1: HUMIDIFIER_CA1_CB1_SENSORS,
    MODEL_AIRPURIFIER_V2: PURIFIER_V2_SENSORS,
    MODEL_AIRPURIFIER_V3: PURIFIER_V3_SENSORS,
    MODEL_AIRPURIFIER_PRO_V7: PURIFIER_PRO_V7_SENSORS,
    MODEL_AIRPURIFIER_PRO: PURIFIER_PRO_SENSORS,
    MODEL_AIRFRESH_VA2: AIRFRESH_SENSORS,
}

VACUUM_SENSORS = {
    ATTR_DND_START: XiaomiMiioSensorDescription(
        key=ATTR_DND_START,
        icon="mdi:fast-forward",
        name="DnD start",
        device_class=DEVICE_CLASS_TIMESTAMP,
        parent_key=KEY_VACUUM_DND_STATUS,
    ),
    ATTR_DND_END: XiaomiMiioSensorDescription(
        key=ATTR_DND_END,
        icon="mdi:fast-forward",
        name="DnD end",
        device_class=DEVICE_CLASS_TIMESTAMP,
        parent_key=KEY_VACUUM_DND_STATUS,
    ),
    ATTR_LAST_CLEAN_START: XiaomiMiioSensorDescription(
        key=ATTR_LAST_CLEAN_START,
        icon="mdi:fast-forward",
        name="Last clean start",
        device_class=DEVICE_CLASS_TIMESTAMP,
        parent_key=KEY_VACUUM_LAST_CLEAN_STATUS,
    ),
    ATTR_LAST_CLEAN_END: XiaomiMiioSensorDescription(
        key=ATTR_LAST_CLEAN_END,
        icon="mdi:fast-forward",
        device_class=DEVICE_CLASS_TIMESTAMP,
        parent_key=KEY_VACUUM_LAST_CLEAN_STATUS,
        name="Last clean end",
    ),
    ATTR_LAST_CLEAN_TIME: XiaomiMiioSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:fast-forward",
        key=ATTR_LAST_CLEAN_TIME,
        parent_key=KEY_VACUUM_LAST_CLEAN_STATUS,
        name="Last clean duration",
    ),
    ATTR_LAST_CLEAN_AREA: XiaomiMiioSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:fast-forward",
        key=ATTR_LAST_CLEAN_AREA,
        parent_key=KEY_VACUUM_LAST_CLEAN_STATUS,
        name="Last clean area",
    ),
    ATTR_CLEAN_HISTORY_TOTAL_DURATION: XiaomiMiioSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:fast-forward",
        key=ATTR_CLEAN_HISTORY_TOTAL_DURATION,
        parent_key=KEY_VACUUM_CLEAN_HISTORY_STATUS,
        name="Clean history total duration",
    ),
    ATTR_CLEAN_HISTORY_TOTAL_AREA: XiaomiMiioSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:fast-forward",
        key=ATTR_CLEAN_HISTORY_TOTAL_AREA,
        parent_key=KEY_VACUUM_CLEAN_HISTORY_STATUS,
        name="Clean history total area",
    ),
    ATTR_CLEAN_HISTORY_COUNT: XiaomiMiioSensorDescription(
        native_unit_of_measurement="",
        icon="mdi:fast-forward",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        key=ATTR_CLEAN_HISTORY_COUNT,
        parent_key=KEY_VACUUM_CLEAN_HISTORY_STATUS,
        name="Clean history count",
    ),
    ATTR_CLEAN_HISTORY_DUST_COLLECTION_COUNT: XiaomiMiioSensorDescription(
        native_unit_of_measurement="",
        icon="mdi:fast-forward",
        state_class="total_increasing",
        key=ATTR_CLEAN_HISTORY_DUST_COLLECTION_COUNT,
        parent_key=KEY_VACUUM_CLEAN_HISTORY_STATUS,
        name="Clean history dust collection count",
    ),
    ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT: XiaomiMiioSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:fast-forward",
        key=ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT,
        parent_key=KEY_VACUUM_CONSUMABLE_STATUS,
        name="Consumable status main brush left",
    ),
    ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT: XiaomiMiioSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:fast-forward",
        key=ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT,
        parent_key=KEY_VACUUM_CONSUMABLE_STATUS,
        name="Consumable status side brush left",
    ),
    ATTR_CONSUMABLE_STATUS_FILTER_LEFT: XiaomiMiioSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:fast-forward",
        key=ATTR_CONSUMABLE_STATUS_FILTER_LEFT,
        parent_key=KEY_VACUUM_CONSUMABLE_STATUS,
        name="Consumable status filter left",
    ),
    ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT: XiaomiMiioSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:fast-forward",
        key=ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT,
        parent_key=KEY_VACUUM_CONSUMABLE_STATUS,
        name="Consumable status sensor dirty left",
    ),
}


def _setup_vacuum_sensors(hass, config_entry, async_add_entities):
    device = hass.data[DOMAIN][config_entry.entry_id].get(KEY_DEVICE)
    entities = []

    for sensor, description in VACUUM_SENSORS.items():
        entities.append(
            XiaomiGenericSensor(
                f"{config_entry.title} {description.name}",
                device,
                config_entry,
                f"{sensor}_{config_entry.unique_id}",
                hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                description,
            )
        )

    async_add_entities(entities)


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
            GATEWAY_MODEL_AQARA,
            GATEWAY_MODEL_EU,
        ]:
            description = SENSOR_TYPES[ATTR_ILLUMINANCE]
            entities.append(
                XiaomiGatewayIlluminanceSensor(
                    gateway, config_entry.title, config_entry.unique_id, description
                )
            )
        # Gateway sub devices
        sub_devices = gateway.devices
        coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
        for sub_device in sub_devices.values():
            for sensor, description in SENSOR_TYPES.items():
                if sensor not in sub_device.status:
                    continue
                entities.append(
                    XiaomiGatewaySensor(
                        coordinator, sub_device, config_entry, description
                    )
                )
    elif config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        model = config_entry.data[CONF_MODEL]
        device = hass.data[DOMAIN][config_entry.entry_id].get(KEY_DEVICE)
        sensors = []
        if model in MODEL_TO_SENSORS_MAP:
            sensors = MODEL_TO_SENSORS_MAP[model]
        elif model in MODELS_HUMIDIFIER_MIOT:
            sensors = HUMIDIFIER_MIOT_SENSORS
        elif model in MODELS_HUMIDIFIER_MJJSQ:
            sensors = HUMIDIFIER_MJJSQ_SENSORS
        elif model in MODELS_HUMIDIFIER_MIIO:
            sensors = HUMIDIFIER_MIIO_SENSORS
        elif model in MODELS_PURIFIER_MIIO:
            sensors = PURIFIER_MIIO_SENSORS
        elif model in MODELS_PURIFIER_MIOT:
            sensors = PURIFIER_MIOT_SENSORS
        elif model in MODELS_VACUUM:
            return _setup_vacuum_sensors(hass, config_entry, async_add_entities)
        else:
            unique_id = config_entry.unique_id
            name = config_entry.title
            _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

            device = AirQualityMonitor(host, token)
            description = SENSOR_TYPES[ATTR_AIR_QUALITY]
            entities.append(
                XiaomiAirQualityMonitor(
                    name, device, config_entry, unique_id, description
                )
            )
        for sensor, description in SENSOR_TYPES.items():
            if sensor not in sensors:
                continue
            entities.append(
                XiaomiGenericSensor(
                    f"{config_entry.title} {description.name}",
                    device,
                    config_entry,
                    f"{sensor}_{config_entry.unique_id}",
                    hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                    description,
                )
            )

    async_add_entities(entities)


class XiaomiGenericSensor(XiaomiCoordinatedMiioEntity, SensorEntity):
    """Representation of a Xiaomi generic sensor."""

    def __init__(
        self,
        name,
        device,
        entry,
        unique_id,
        coordinator,
        description: XiaomiMiioSensorDescription,
    ):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_icon = description.icon
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_entity_registry_enabled_default = False
        self.entity_description: XiaomiMiioSensorDescription = description

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.entity_description.parent_key is not None:
            return self._extract_value_from_attribute(
                self.coordinator.data[self.entity_description.parent_key],
                self.entity_description.key,
            )

        return self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            attr: self._extract_value_from_attribute(self.coordinator.data, attr)
            for attr in self.entity_description.attributes
            if hasattr(self.coordinator.data, attr)
        }

    @classmethod
    def _extract_value_from_attribute(cls, state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime.timedelta):
            return cls._parse_time_delta(value)
        if isinstance(value, datetime.time):
            return cls._parse_datetime_time(value)
        if isinstance(value, datetime.datetime):
            return cls._parse_datetime_datetime(value)
        if isinstance(value, datetime.timedelta):
            return cls._parse_time_delta(value)
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return value

        _LOGGER.warning(
            f"could not determine how to parse state value of type: {type(value)}"
        )

        return value

    @staticmethod
    def _parse_time_delta(timedelta: datetime.timedelta) -> int:
        return timedelta.seconds

    @staticmethod
    def _parse_datetime_time(time: datetime.time) -> str:
        time = datetime.datetime.now().replace(
            hour=time.hour, minute=time.minute, second=0, microsecond=0
        )

        if time < datetime.datetime.now():
            time += datetime.timedelta(days=1)

        return time.isoformat()

    @staticmethod
    def _parse_datetime_datetime(time: datetime.datetime) -> str:
        return time.isoformat()

    @staticmethod
    def _parse_datetime_timedelta(time: datetime.timedelta) -> int:
        return time.seconds


class XiaomiAirQualityMonitor(XiaomiMiioEntity, SensorEntity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, name, device, entry, unique_id, description):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id)

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
        self.entity_description = description

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def native_value(self):
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

    def __init__(self, coordinator, sub_device, entry, description):
        """Initialize the XiaomiSensor."""
        super().__init__(coordinator, sub_device, entry)
        self._unique_id = f"{sub_device.sid}-{description.key}"
        self._name = f"{description.key} ({sub_device.sid})".capitalize()
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._sub_device.status[self.entity_description.key]


class XiaomiGatewayIlluminanceSensor(SensorEntity):
    """Representation of the gateway device's illuminance sensor."""

    def __init__(self, gateway_device, gateway_name, gateway_device_id, description):
        """Initialize the entity."""

        self._attr_name = f"{gateway_name} {description.name}"
        self._attr_unique_id = f"{gateway_device_id}-{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, gateway_device_id)}}
        self._gateway = gateway_device
        self.entity_description = description
        self._available = False
        self._state = None

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def native_value(self):
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
