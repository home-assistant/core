"""Support for RFXtrx sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from RFXtrx import ControlEvent, SensorEvent

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_DEVICES,
    DEGREE,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    POWER_WATT,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UV_INDEX,
)
from homeassistant.core import callback

from . import (
    CONF_DATA_BITS,
    RfxtrxEntity,
    connect_auto_add,
    get_device_id,
    get_rfx_object,
)
from .const import ATTR_EVENT

_LOGGER = logging.getLogger(__name__)


def _battery_convert(value):
    """Battery is given as a value between 0 and 9."""
    if value is None:
        return None
    return (value + 1) * 10


def _rssi_convert(value):
    """Rssi is given as dBm value."""
    if value is None:
        return None
    return f"{value*8-120}"


@dataclass
class RfxtrxSensorEntityDescription(SensorEntityDescription):
    """Description of sensor entities."""

    convert: Callable = lambda x: x


SENSOR_TYPES = (
    RfxtrxSensorEntityDescription(
        key="Barometer",
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PRESSURE_HPA,
    ),
    RfxtrxSensorEntityDescription(
        key="Battery numeric",
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        convert=_battery_convert,
    ),
    RfxtrxSensorEntityDescription(
        key="Current",
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 1",
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 2",
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 3",
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Energy usage",
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    RfxtrxSensorEntityDescription(
        key="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    RfxtrxSensorEntityDescription(
        key="Rssi numeric",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        convert=_rssi_convert,
    ),
    RfxtrxSensorEntityDescription(
        key="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Temperature2",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Total usage",
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    RfxtrxSensorEntityDescription(
        key="Voltage",
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind direction",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DEGREE,
    ),
    RfxtrxSensorEntityDescription(
        key="Rain rate",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PRECIPITATION_MILLIMETERS_PER_HOUR,
    ),
    RfxtrxSensorEntityDescription(
        key="Sound",
    ),
    RfxtrxSensorEntityDescription(
        key="Sensor Status",
    ),
    RfxtrxSensorEntityDescription(
        key="Count",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement="count",
    ),
    RfxtrxSensorEntityDescription(
        key="Counter value",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement="count",
    ),
    RfxtrxSensorEntityDescription(
        key="Chill",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind average speed",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind gust",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
    ),
    RfxtrxSensorEntityDescription(
        key="Rain total",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
    ),
    RfxtrxSensorEntityDescription(
        key="Forecast",
    ),
    RfxtrxSensorEntityDescription(
        key="Forecast numeric",
    ),
    RfxtrxSensorEntityDescription(
        key="Humidity status",
    ),
    RfxtrxSensorEntityDescription(
        key="UV",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
    ),
)

SENSOR_TYPES_DICT = {desc.key: desc for desc in SENSOR_TYPES}


async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities,
):
    """Set up platform."""
    discovery_info = config_entry.data
    data_ids = set()

    def supported(event):
        return isinstance(event, (ControlEvent, SensorEvent))

    entities = []
    for packet_id, entity_info in discovery_info[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(
            event.device, data_bits=entity_info.get(CONF_DATA_BITS)
        )
        for data_type in set(event.values) & set(SENSOR_TYPES_DICT):
            data_id = (*device_id, data_type)
            if data_id in data_ids:
                continue
            data_ids.add(data_id)

            entity = RfxtrxSensor(event.device, device_id, SENSOR_TYPES_DICT[data_type])
            entities.append(entity)

    async_add_entities(entities)

    @callback
    def sensor_update(event, device_id):
        """Handle sensor updates from the RFXtrx gateway."""
        if not supported(event):
            return

        for data_type in set(event.values) & set(SENSOR_TYPES_DICT):
            data_id = (*device_id, data_type)
            if data_id in data_ids:
                continue
            data_ids.add(data_id)

            _LOGGER.info(
                "Added sensor (Device ID: %s Class: %s Sub: %s, Event: %s)",
                event.device.id_string.lower(),
                event.device.__class__.__name__,
                event.device.subtype,
                "".join(f"{x:02x}" for x in event.data),
            )

            entity = RfxtrxSensor(
                event.device, device_id, SENSOR_TYPES_DICT[data_type], event=event
            )
            async_add_entities([entity])

    # Subscribe to main RFXtrx events
    connect_auto_add(hass, discovery_info, sensor_update)


class RfxtrxSensor(RfxtrxEntity, SensorEntity):
    """Representation of a RFXtrx sensor."""

    entity_description: RfxtrxSensorEntityDescription

    def __init__(self, device, device_id, entity_description, event=None):
        """Initialize the sensor."""
        super().__init__(device, device_id, event=event)
        self.entity_description = entity_description
        self._name = f"{device.type_string} {device.id_string} {entity_description.key}"
        self._unique_id = "_".join(
            x for x in (*self._device_id, entity_description.key)
        )

    async def async_added_to_hass(self):
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                event = old_state.attributes.get(ATTR_EVENT)
                if event:
                    self._apply_event(get_rfx_object(event))

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self._event:
            return None
        value = self._event.values.get(self.entity_description.key)
        return self.entity_description.convert(value)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def force_update(self) -> bool:
        """We should force updates. Repeated states have meaning."""
        return True

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if device_id != self._device_id:
            return

        if self.entity_description.key not in event.values:
            return

        _LOGGER.debug(
            "Sensor update (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string,
            event.device.__class__.__name__,
            event.device.subtype,
        )

        self._apply_event(event)

        self.async_write_ha_state()
