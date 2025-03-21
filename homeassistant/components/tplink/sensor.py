"""Support for TPLink sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import methodcaller
from typing import TYPE_CHECKING, Any, cast

from kasa import Feature
from kasa.smart.modules.clean import ErrorCode as VacuumError

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry
from .const import UNIT_MAPPING
from .entity import CoordinatedTPLinkFeatureEntity, TPLinkFeatureEntityDescription


@dataclass(frozen=True, kw_only=True)
class TPLinkSensorEntityDescription(
    SensorEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based sensor entity description."""

    #: Optional callable to convert the value
    convert_fn: Callable[[Any], Any] | None = None


# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_TOTAL_SECONDS_METHOD_CALLER = methodcaller("total_seconds")

SENSOR_DESCRIPTIONS: tuple[TPLinkSensorEntityDescription, ...] = (
    TPLinkSensorEntityDescription(
        key="current_consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="consumption_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        key="consumption_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        key="consumption_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        # Disable as the value reported by the device changes seconds frequently
        entity_registry_enabled_default=False,
        key="on_since",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="signal_level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="ssid",
    ),
    TPLinkSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="auto_off_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="device_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="water_alert_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="report_interval",
        device_class=SensorDeviceClass.DURATION,
    ),
    TPLinkSensorEntityDescription(
        key="alarm_source",
    ),
    # Vacuum cleaning records
    TPLinkSensorEntityDescription(
        key="clean_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        key="clean_area",
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="clean_progress",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="last_clean_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        key="last_clean_area",
        device_class=SensorDeviceClass.AREA,
    ),
    TPLinkSensorEntityDescription(
        key="last_clean_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="total_clean_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="total_clean_area",
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        key="total_clean_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="main_brush_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="main_brush_used",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="side_brush_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="side_brush_used",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="filter_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="filter_used",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="sensor_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="sensor_used",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="charging_contacts_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="charging_contacts_used",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        convert_fn=_TOTAL_SECONDS_METHOD_CALLER,
    ),
    TPLinkSensorEntityDescription(
        key="vacuum_error",
        device_class=SensorDeviceClass.ENUM,
        options=[name.lower() for name in VacuumError._member_names_],
        convert_fn=lambda x: x.name.lower(),
    ),
)

SENSOR_DESCRIPTIONS_MAP = {desc.key: desc for desc in SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device
    known_child_device_ids: set[str] = set()
    first_check = True

    def _check_device() -> None:
        entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            feature_type=Feature.Type.Sensor,
            entity_class=TPLinkSensorEntity,
            descriptions=SENSOR_DESCRIPTIONS_MAP,
            platform_domain=SENSOR_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkSensorEntity(CoordinatedTPLinkFeatureEntity, SensorEntity):
    """Representation of a feature-based TPLink sensor."""

    entity_description: TPLinkSensorEntityDescription

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        value = self._feature.value
        if value is not None and self._feature.precision_hint is not None:
            value = round(cast(float, value), self._feature.precision_hint)
            # We probably do not need this, when we are rounding already?
            self._attr_suggested_display_precision = self._feature.precision_hint

        if self.entity_description.convert_fn:
            value = self.entity_description.convert_fn(value)

        if TYPE_CHECKING:
            # pylint: disable-next=import-outside-toplevel
            from datetime import date, datetime

            assert isinstance(value, str | int | float | date | datetime | None)

        self._attr_native_value = value
        # Map to homeassistant units and fallback to upstream one if none found
        if (unit := self._feature.unit) is not None:
            self._attr_native_unit_of_measurement = UNIT_MAPPING.get(unit, unit)
        return True
