"""Sensor platform for the Rotarex integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


def get_tank_name(tank_data: dict[str, Any] | None) -> str:
    """Generate a name for the tank from the available data."""
    if tank_data and tank_data.get("Name"):
        return tank_data["Name"]
    if tank_data:
        return f"Tank {tank_data.get('Guid', 'Unknown')}"
    return "Unknown Tank"


@dataclass(kw_only=True, frozen=True)
class RotarexTankSensorEntityDescription(SensorEntityDescription):
    """Describes Rotarex tank sensors."""

    value_fn: Callable[[dict[str, Any] | None], Any]
    extra_attr_fn: Callable[[dict[str, Any] | None], dict[str, Any] | None] | None = (
        None
    )


SENSOR_DESCRIPTIONS: tuple[RotarexTankSensorEntityDescription, ...] = (
    RotarexTankSensorEntityDescription(
        key="level",
        translation_key="level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync.get("Level") if sync else None,
        extra_attr_fn=lambda sync: {
            "last_sync": sync.get("SynchDate"),
            "temperature": sync.get("Temperature"),
        }
        if sync
        else None,
    ),
    RotarexTankSensorEntityDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync.get("Battery") if sync else None,
        extra_attr_fn=lambda sync: {"last_sync": sync.get("SynchDate")}
        if sync
        else None,
    ),
    RotarexTankSensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sync: (
            dt_util.as_local(dt_util.parse_datetime(sync["SynchDate"]))
            if sync and sync.get("SynchDate")
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    if not isinstance(coordinator.data, list):
        return

    async_add_entities(
        RotarexTankSensor(coordinator, tank, description)
        for tank in coordinator.data
        if isinstance(tank, dict) and tank.get("Guid")
        for description in SENSOR_DESCRIPTIONS
    )


class RotarexTankSensor(CoordinatorEntity, SensorEntity):
    """Generic Rotarex tank sensor."""

    entity_description: RotarexTankSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        tank_data: dict[str, Any],
        description: RotarexTankSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._tank_id = tank_data["Guid"]
        self._attr_unique_id = f"rotarex_{self._tank_id}_{description.key}"
        self._update_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_state()
        self.async_write_ha_state()

    def _get_latest_sync(self) -> dict[str, Any] | None:
        """Return the most recent sync data."""
        data = self.coordinator.data
        if not isinstance(data, list):
            return None

        tank = next(
            (t for t in data if isinstance(t, dict) and t.get("Guid") == self._tank_id),
            None,
        )
        synch_datas = tank.get("SynchDatas") if tank else None
        if isinstance(synch_datas, list) and synch_datas:
            return max(synch_datas, key=lambda x: x.get("SynchDate", ""))
        return None

    def _update_state(self) -> None:
        """Update native value from coordinator data."""
        latest_sync = self._get_latest_sync()
        self._attr_native_value = self.entity_description.value_fn(latest_sync)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.extra_attr_fn:
            return self.entity_description.extra_attr_fn(self._get_latest_sync())
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self.coordinator.data
        tank_data = next(
            (t for t in data if isinstance(t, dict) and t.get("Guid") == self._tank_id),
            None,
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._tank_id)},
            name=get_tank_name(tank_data),
            manufacturer="Rotarex",
            model="DIMES SRG",
        )
