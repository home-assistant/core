"""Support for RFXtrx sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any, cast

from RFXtrx import ControlEvent, RFXtrxDevice, RFXtrxEvent, SensorEvent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DeviceTuple, RfxtrxEntity, async_setup_platform_entry, get_rfx_object
from .const import ATTR_EVENT

_LOGGER = logging.getLogger(__name__)


def _battery_convert(value: int | None) -> int | None:
    """Battery is given as a value between 0 and 9."""
    if value is None:
        return None
    return (value + 1) * 10


def _rssi_convert(value: int | None) -> str | None:
    """Rssi is given as dBm value."""
    if value is None:
        return None
    return f"{value*8-120}"


@dataclass
class RfxtrxSensorEntityDescription(SensorEntityDescription):
    """Description of sensor entities."""

    convert: Callable[[Any], StateType | date | datetime | Decimal] = lambda x: cast(
        StateType, x
    )


SENSOR_TYPES = (
    RfxtrxSensorEntityDescription(
        key="Barometer",
        name="Barometer",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRESSURE_HPA,
    ),
    RfxtrxSensorEntityDescription(
        key="Battery numeric",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        convert=_battery_convert,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RfxtrxSensorEntityDescription(
        key="Current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 1",
        name="Current Ch. 1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 2",
        name="Current Ch. 2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 3",
        name="Current Ch. 3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Energy usage",
        name="Instantaneous power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    RfxtrxSensorEntityDescription(
        key="Humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    RfxtrxSensorEntityDescription(
        key="Rssi numeric",
        name="Signal strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        convert=_rssi_convert,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RfxtrxSensorEntityDescription(
        key="Temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Temperature2",
        name="Temperature 2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Total usage",
        name="Total energy usage",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    RfxtrxSensorEntityDescription(
        key="Voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind direction",
        name="Wind direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
    ),
    RfxtrxSensorEntityDescription(
        key="Rain rate",
        name="Rain rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRECIPITATION_MILLIMETERS_PER_HOUR,
    ),
    RfxtrxSensorEntityDescription(
        key="Sound",
        name="Sound",
    ),
    RfxtrxSensorEntityDescription(
        key="Sensor Status",
        name="Sensor status",
    ),
    RfxtrxSensorEntityDescription(
        key="Count",
        name="Count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="count",
    ),
    RfxtrxSensorEntityDescription(
        key="Counter value",
        name="Counter value",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="count",
    ),
    RfxtrxSensorEntityDescription(
        key="Chill",
        name="Chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind average speed",
        name="Wind average speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind gust",
        name="Wind gust",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
    ),
    RfxtrxSensorEntityDescription(
        key="Rain total",
        name="Rain total",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
    ),
    RfxtrxSensorEntityDescription(
        key="Forecast",
        name="Forecast status",
    ),
    RfxtrxSensorEntityDescription(
        key="Forecast numeric",
        name="Forecast",
    ),
    RfxtrxSensorEntityDescription(
        key="Humidity status",
        name="Humidity status",
    ),
    RfxtrxSensorEntityDescription(
        key="UV",
        name="UV index",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
    ),
)

SENSOR_TYPES_DICT = {desc.key: desc for desc in SENSOR_TYPES}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up config entry."""

    def _supported(event: RFXtrxEvent) -> bool:
        return isinstance(event, (ControlEvent, SensorEvent))

    def _constructor(
        event: RFXtrxEvent,
        auto: RFXtrxEvent | None,
        device_id: DeviceTuple,
        entity_info: dict[str, Any],
    ) -> list[Entity]:
        entities: list[Entity] = []
        for data_type in set(event.values) & set(SENSOR_TYPES_DICT):
            entities.append(
                RfxtrxSensor(
                    event.device,
                    device_id,
                    SENSOR_TYPES_DICT[data_type],
                    event=event if auto else None,
                )
            )

        return entities

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, _supported, _constructor
    )


class RfxtrxSensor(RfxtrxEntity, SensorEntity):
    """Representation of a RFXtrx sensor.

    Since all repeated events have meaning, these types of sensors
    need to have force update enabled.
    """

    _attr_force_update = True
    entity_description: RfxtrxSensorEntityDescription

    def __init__(
        self,
        device: RFXtrxDevice,
        device_id: DeviceTuple,
        entity_description: RfxtrxSensorEntityDescription,
        event: RFXtrxEvent | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_id, event=event)
        self.entity_description = entity_description
        self._attr_unique_id = "_".join(x for x in (*device_id, entity_description.key))

    async def async_added_to_hass(self) -> None:
        """Restore device state."""
        await super().async_added_to_hass()

        if (
            self._event is None
            and (old_state := await self.async_get_last_state()) is not None
            and (event := old_state.attributes.get(ATTR_EVENT))
        ):
            self._apply_event(get_rfx_object(event))

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the state of the sensor."""
        if not self._event:
            return None
        value = self._event.values.get(self.entity_description.key)
        return self.entity_description.convert(value)

    @callback
    def _handle_event(self, event: RFXtrxEvent, device_id: DeviceTuple) -> None:
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
