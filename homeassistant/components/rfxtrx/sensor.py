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
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UV_INDEX,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DeviceTuple, async_setup_platform_entry, get_rfx_object
from .const import ATTR_EVENT
from .entity import RfxtrxEntity

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


@dataclass(frozen=True)
class RfxtrxSensorEntityDescription(SensorEntityDescription):
    """Description of sensor entities."""

    convert: Callable[[Any], StateType | date | datetime | Decimal] = lambda x: cast(
        StateType, x
    )


SENSOR_TYPES = (
    RfxtrxSensorEntityDescription(
        key="Barometer",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    RfxtrxSensorEntityDescription(
        key="Battery numeric",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        convert=_battery_convert,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RfxtrxSensorEntityDescription(
        key="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 1",
        translation_key="current_ch_1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 2",
        translation_key="current_ch_2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Current Ch. 3",
        translation_key="current_ch_3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    RfxtrxSensorEntityDescription(
        key="Energy usage",
        translation_key="instantaneous_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    RfxtrxSensorEntityDescription(
        key="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    RfxtrxSensorEntityDescription(
        key="Rssi numeric",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        convert=_rssi_convert,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RfxtrxSensorEntityDescription(
        key="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Temperature2",
        translation_key="temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Total usage",
        translation_key="total_energy_usage",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    RfxtrxSensorEntityDescription(
        key="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind direction",
        translation_key="wind_direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
    ),
    RfxtrxSensorEntityDescription(
        key="Rain rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    RfxtrxSensorEntityDescription(
        key="Sound",
        translation_key="sound",
    ),
    RfxtrxSensorEntityDescription(
        key="Sensor Status",
        translation_key="sensor_status",
    ),
    RfxtrxSensorEntityDescription(
        key="Count",
        translation_key="count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RfxtrxSensorEntityDescription(
        key="Counter value",
        translation_key="counter_value",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RfxtrxSensorEntityDescription(
        key="Chill",
        translation_key="chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind average speed",
        translation_key="wind_average_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    RfxtrxSensorEntityDescription(
        key="Wind gust",
        translation_key="wind_gust",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    RfxtrxSensorEntityDescription(
        key="Rain total",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    RfxtrxSensorEntityDescription(
        key="Forecast",
        translation_key="forecast_status",
    ),
    RfxtrxSensorEntityDescription(
        key="Forecast numeric",
        translation_key="forecast",
    ),
    RfxtrxSensorEntityDescription(
        key="Humidity status",
        translation_key="humidity_status",
    ),
    RfxtrxSensorEntityDescription(
        key="UV",
        translation_key="uv_index",
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
        return [
            RfxtrxSensor(
                event.device,
                device_id,
                SENSOR_TYPES_DICT[data_type],
                event=event if auto else None,
            )
            for data_type in set(event.values) & set(SENSOR_TYPES_DICT)
        ]

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, _supported, _constructor
    )


# pylint: disable-next=hass-invalid-inheritance # needs fixing
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
