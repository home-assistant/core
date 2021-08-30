"""Support for EnOcean sensors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ID,
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    STATE_CLOSED,
    STATE_OPEN,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .device import EnOceanEntity

CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_MIN_ILLUMINANCE = "min_illuminance"
CONF_MAX_ILLUMINANCE = "max_illuminance"
CONF_RANGE_FROM = "range_from"
CONF_RANGE_TO = "range_to"
CONF_DATA_BYTE = "data_byte"
CONF_PACKET_FILTER = "packet_filter"
CONF_MASK = "mask"
CONF_VALUE = "value"

DEFAULT_NAME = "EnOcean sensor"

SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_ILLUMINANCE = "illuminance"
SENSOR_TYPE_POWER = "powersensor"
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_WINDOWHANDLE = "windowhandle"

SENSOR_DESC_HUMIDITY = SensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    name="Humidity",
    native_unit_of_measurement=PERCENTAGE,
    icon="mdi:water-percent",
    device_class=DEVICE_CLASS_HUMIDITY,
)

SENSOR_DESC_ILLUMINANCE = SensorEntityDescription(
    key=SENSOR_TYPE_ILLUMINANCE,
    name="Illuminance",
    native_unit_of_measurement=LIGHT_LUX,
    icon="mdi:brightness-7",
    device_class=DEVICE_CLASS_ILLUMINANCE,
)

SENSOR_DESC_TEMPERATURE = SensorEntityDescription(
    key=SENSOR_TYPE_TEMPERATURE,
    name="Temperature",
    native_unit_of_measurement=TEMP_CELSIUS,
    icon="mdi:thermometer",
    device_class=DEVICE_CLASS_TEMPERATURE,
    state_class=STATE_CLASS_MEASUREMENT,
)

SENSOR_DESC_HUMIDITY = SensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    name="Humidity",
    native_unit_of_measurement=PERCENTAGE,
    icon="mdi:water-percent",
    device_class=DEVICE_CLASS_HUMIDITY,
    state_class=STATE_CLASS_MEASUREMENT,
)

SENSOR_DESC_POWER = SensorEntityDescription(
    key=SENSOR_TYPE_POWER,
    name="Power",
    native_unit_of_measurement=POWER_WATT,
    icon="mdi:power-plug",
    device_class=DEVICE_CLASS_POWER,
    state_class=STATE_CLASS_MEASUREMENT,
)

SENSOR_DESC_WINDOWHANDLE = SensorEntityDescription(
    key=SENSOR_TYPE_WINDOWHANDLE,
    name="WindowHandle",
    icon="mdi:window",
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS, default=SENSOR_TYPE_POWER): cv.string,
        vol.Optional(CONF_MAX_TEMP, default=40): vol.Coerce(int),
        vol.Optional(CONF_MIN_TEMP, default=0): vol.Coerce(int),
        vol.Optional(CONF_RANGE_FROM, default=255): cv.positive_int,
        vol.Optional(CONF_RANGE_TO, default=0): cv.positive_int,
        vol.Optional(CONF_DATA_BYTE, default=3): cv.positive_int,
        vol.Optional(CONF_MAX_ILLUMINANCE, default=1000): vol.Coerce(int),
        vol.Optional(CONF_MIN_ILLUMINANCE, default=0): vol.Coerce(int),
        vol.Optional(CONF_PACKET_FILTER): vol.Maybe(
            {
                vol.Required(CONF_MASK): vol.All(cv.ensure_list, [vol.Coerce(int)]),
                vol.Required(CONF_VALUE): vol.All(cv.ensure_list, [vol.Coerce(int)]),
            }
        ),
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an EnOcean sensor device."""
    dev_id = config[CONF_ID]
    dev_name = config[CONF_NAME]
    sensor_type = config[CONF_DEVICE_CLASS]

    entities: list[EnOceanSensor] = []
    if sensor_type == SENSOR_TYPE_TEMPERATURE:
        temp_min = config[CONF_MIN_TEMP]
        temp_max = config[CONF_MAX_TEMP]
        range_from = config[CONF_RANGE_FROM]
        range_to = config[CONF_RANGE_TO]
        data_byte = config.get(CONF_DATA_BYTE)
        packet_filter = config.get(CONF_PACKET_FILTER)
        entities = [
            EnOceanTemperatureSensor(
                dev_id,
                dev_name,
                SENSOR_DESC_TEMPERATURE,
                scale_min=temp_min,
                scale_max=temp_max,
                range_from=range_from,
                range_to=range_to,
                data_byte=data_byte,
                packet_filter=packet_filter
            )
        ]

    elif sensor_type == SENSOR_TYPE_ILLUMINANCE:
        illuminance_min = config.get(CONF_MIN_ILLUMINANCE)
        illuminance_max = config.get(CONF_MAX_ILLUMINANCE)
        range_from = config.get(CONF_RANGE_FROM)
        range_to = config.get(CONF_RANGE_TO)
        data_byte = config.get(CONF_DATA_BYTE)
        packet_filter = config.get(CONF_PACKET_FILTER)
        entities = [
                EnOceanIlluminanceSensor(
                    dev_id,
                    dev_name,
                    illuminance_min,
                    illuminance_max,
                    range_from=range_from,
                    range_to=range_to,
                    data_byte=data_byte,
                    packet_filter=packet_filter
                )
            ]

    elif sensor_type == SENSOR_TYPE_HUMIDITY:
        entities = [EnOceanHumiditySensor(dev_id, dev_name, SENSOR_DESC_HUMIDITY)]

    elif sensor_type == SENSOR_TYPE_POWER:
        entities = [EnOceanPowerSensor(dev_id, dev_name, SENSOR_DESC_POWER)]

    elif sensor_type == SENSOR_TYPE_WINDOWHANDLE:
        entities = [EnOceanWindowHandle(dev_id, dev_name, SENSOR_DESC_WINDOWHANDLE)]

    if entities:
        add_entities(entities)


class EnOceanSensor(EnOceanEntity, RestoreEntity, SensorEntity):
    """Representation of an  EnOcean sensor device such as a power meter."""

    def __init__(self, dev_id, dev_name, description: SensorEntityDescription):
        """Initialize the EnOcean sensor device."""
        super().__init__(dev_id, dev_name)
        self.entity_description = description
        self._attr_name = f"{description.name} {dev_name}"

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        if (state := await self.async_get_last_state()) is not None:
            self._attr_native_value = state.state

    def value_changed(self, packet):
        """Update the internal state of the sensor."""


class EnOceanPowerSensor(EnOceanSensor):
    """Representation of an EnOcean power sensor.

    EEPs (EnOcean Equipment Profiles):
    - A5-12-01 (Automated Meter Reading, Electricity)
    """

    def value_changed(self, packet):
        """Update the internal state of the sensor."""
        if packet.rorg != 0xA5:
            return
        packet.parse_eep(0x12, 0x01)
        if packet.parsed["DT"]["raw_value"] == 1:
            # this packet reports the current value
            raw_val = packet.parsed["MR"]["raw_value"]
            divisor = packet.parsed["DIV"]["raw_value"]
            self._attr_native_value = raw_val / (10 ** divisor)
            self.schedule_update_ha_state()


class EnOceanMinMaxWithScaleAndDatabyteSensor(EnOceanSensor):
    """Representation of an EnOcean sensor reading value from a data byte, configurable with a min-max value and allowed data range."""

    def __init__(
        self,
        dev_id,
        dev_name,
        sensor_type,
        scale_min,
        scale_max,
        range_from,
        range_to,
        data_byte,
        packet_filter,
    ):
        """Initialize the EnOcean temperature sensor device."""
        super().__init__(dev_id, dev_name, sensor_type)
        self._scale_min = scale_min
        self._scale_max = scale_max
        self.range_from = range_from
        self.range_to = range_to
        self.data_byte = data_byte
        self.packet_filter: dict[str, Any] = packet_filter

    def value_changed(self, packet):
        """Update the internal state of the sensor."""
        if self.packet_filter:
            for data, mask, value in zip(
                packet.data,
                self.packet_filter[CONF_MASK],
                self.packet_filter[CONF_VALUE],
            ):
                if mask == 0xFF and data != value:
                    return

        scalescale = self._scale_max - self._scale_min
        range = self.range_to - self.range_from
        raw_val = packet.data[self.data_byte]
        value = scalescale / range * (raw_val - self.range_from)
        value += self._scale_min
        self._state = round(value, 1)
        self.schedule_update_ha_state()


class EnOceanTemperatureSensor(EnOceanMinMaxWithScaleAndDatabyteSensor):
    """Representation of an EnOcean temperature sensor device.

    EEPs (EnOcean Equipment Profiles):
    - A5-02-01 to A5-02-1B All 8 Bit Temperature Sensors of A5-02
    - A5-10-01 to A5-10-14 (Room Operating Panels)
    - A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)
    - A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)
    - A5-10-10 (Temp. and Humidity Sensor and Set Point)
    - A5-10-12 (Temp. and Humidity Sensor, Set Point and Occupancy Control)
    - 10 Bit Temp. Sensors are not supported (A5-02-20, A5-02-30)

    For the following EEPs the scales must be set to "0 to 250":
    - A5-04-01
    - A5-04-02
    - A5-10-10 to A5-10-14
    """

    def __init__(
        self,
        dev_id,
        dev_name,
        description: SensorEntityDescription,
        *,
        scale_min,
        scale_max,
        range_from,
        range_to,
        data_byte,
        packet_filter,
    ):
        """Initialize the EnOcean temperature sensor device."""
        super().__init__(
            dev_id,
            dev_name,
            SENSOR_TYPE_TEMPERATURE,
            scale_min,
            scale_max,
            range_from,
            range_to,
            data_byte,
            packet_filter,
        )


class EnOceanHumiditySensor(EnOceanSensor):
    """Representation of an EnOcean humidity sensor device.

    EEPs (EnOcean Equipment Profiles):
    - A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)
    - A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)
    - A5-10-10 to A5-10-14 (Room Operating Panels)
    """

    def value_changed(self, packet):
        """Update the internal state of the sensor."""
        if packet.rorg != 0xA5:
            return
        humidity = packet.data[2] * 100 / 250
        self._attr_native_value = round(humidity, 1)
        self.schedule_update_ha_state()


class EnOceanIlluminanceSensor(EnOceanMinMaxWithScaleAndDatabyteSensor):
    """Representation of an EnOcean light sensor device.

    EEPs (EnOcean Equipment Profiles):

    EEPs with a scale from 0 to 255:
    - A5-06-01 (300 to 30000 lx)
    - A5-06-02 (0 to 510 lx)
    - A5-06-05 (0 to 5100 lx)
    - A5-08-01 (0 to 510 lx)
    - A5-08-02 (0 to 1020 lx)
    - A5-08-03 (0 to 1530 lx)

    For the following EEPs the scales must be set to 0 to 250:
    - A5-10-1B (0 to 1000 lx)
    - A5-14-02 (0 to 1000 lx)
    - A5-14-04 (0 to 1000 lx)
    - A5-14-06 (0 to 1000 lx)

    For the following EEPs the scales must be set to 0 to 1000:
    - A5-06-03 (0 to 1000 lx)
    - A5-07-04 (0 to 1000 lx)

    For the following EEPs the databit must be set to 1 and scale set to 0 to 250:
    - A5-10-18 (0 to 1000 lx)
    - A5-10-1C (0 to 1000 lx)
    """

    def __init__(
        self,
        dev_id,
        dev_name,
        scale_min,
        scale_max,
        range_from,
        range_to,
        data_byte,
        packet_filter,
    ):
        """Initialize the EnOcean temperature sensor device."""
        super().__init__(
            dev_id,
            dev_name,
            SENSOR_TYPE_ILLUMINANCE,
            scale_min,
            scale_max,
            range_from,
            range_to,
            data_byte,
            packet_filter,
        )


class EnOceanWindowHandle(EnOceanSensor):
    """Representation of an EnOcean window handle device.

    EEPs (EnOcean Equipment Profiles):
    - F6-10-00 (Mechanical handle / Hoppe AG)
    """

    def value_changed(self, packet):
        """Update the internal state of the sensor."""

        action = (packet.data[1] & 0x70) >> 4

        if action == 0x07:
            self._attr_native_value = STATE_CLOSED
        if action in (0x04, 0x06):
            self._attr_native_value = STATE_OPEN
        if action == 0x05:
            self._attr_native_value = "tilt"

        self.schedule_update_ha_state()
