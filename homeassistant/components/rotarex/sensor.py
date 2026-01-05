# homeassistant/components/rotarex/sensor.py
"""Sensor platform for the Rotarex integration."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
    entities: list[SensorEntity] = []

    if isinstance(coordinator.data, list):
        for tank_data in coordinator.data:
            if isinstance(tank_data, dict) and tank_data.get("Guid"):
                entities.append(TankLevelSensor(coordinator, tank_data))
                entities.append(TankBatterySensor(coordinator, tank_data))
                entities.append(TankLastSyncDateSensor(coordinator, tank_data))

    async_add_entities(entities)


class BaseTankSensor(CoordinatorEntity, SensorEntity):
    """Base class for Rotarex tank sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, tank_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._tank_id = tank_data["Guid"]
        self._update_internal_state(tank_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            for tank_data in self.coordinator.data:
                if (
                    isinstance(tank_data, dict)
                    and tank_data.get("Guid") == self._tank_id
                ):
                    self._update_internal_state(tank_data)
                    self.async_write_ha_state()
                    break

    def _update_internal_state(self, tank_data: dict[str, Any]) -> None:
        """Update sensor's internal state from tank_data."""
        raise NotImplementedError

    def _get_latest_sync(self) -> dict[str, Any] | None:
        """Get the latest sync data for the tank."""
        data = self.coordinator.data
        if not isinstance(data, list):
            return None

        tank_data = next(
            (
                tank
                for tank in data
                if isinstance(tank, dict) and tank.get("Guid") == self._tank_id
            ),
            None,
        )

        synch_datas = tank_data.get("SynchDatas") if tank_data else None
        if isinstance(synch_datas, list):
            return max(synch_datas, key=lambda x: x.get("SynchDate", ""))

        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self.coordinator.data
        tank_data: dict[str, Any] | None = None

        if isinstance(data, list):
            tank_data = next(
                (
                    tank
                    for tank in data
                    if isinstance(tank, dict) and tank.get("Guid") == self._tank_id
                ),
                None,
            )

        device_name = get_tank_name(tank_data) if tank_data else f"Tank {self._tank_id}"

        return DeviceInfo(
            identifiers={(DOMAIN, self._tank_id)},
            name=device_name,
            manufacturer="Rotarex",
            model="DIMES SRG",
        )


class TankLevelSensor(BaseTankSensor):
    """Representation of a Tank Level Sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.VOLUME_STORAGE
    _attr_translation_key = "level"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        latest_sync = self._get_latest_sync()
        if not latest_sync:
            return None
        return {
            "last_sync": latest_sync.get("SynchDate"),
            "temperature": latest_sync.get("Temperature"),
        }

    def _update_internal_state(self, tank_data: dict[str, Any]) -> None:
        """Update sensor's internal state from tank_data."""
        self._attr_unique_id = f"rotarex_{self._tank_id}_level"
        latest_sync = self._get_latest_sync()
        if latest_sync:
            self._attr_native_value = latest_sync.get("Level")
        else:
            self._attr_native_value = None


class TankBatterySensor(BaseTankSensor):
    """Representation of a Tank Battery Sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_translation_key = "battery"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        latest_sync = self._get_latest_sync()
        if not latest_sync:
            return None
        return {
            "last_sync": latest_sync.get("SynchDate"),
        }

    def _update_internal_state(self, tank_data: dict[str, Any]) -> None:
        """Update sensor's internal state from tank_data."""
        self._attr_unique_id = f"rotarex_{self._tank_id}_battery"
        latest_sync = self._get_latest_sync()
        if latest_sync:
            self._attr_native_value = latest_sync.get("Battery")
        else:
            self._attr_native_value = None


class TankLastSyncDateSensor(BaseTankSensor):
    """Representation of a Tank Last Sync Date Sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_sync"

    def _update_internal_state(self, tank_data: dict[str, Any]) -> None:
        """Update sensor's internal state from tank_data."""
        self._attr_unique_id = f"rotarex_{self._tank_id}_last_sync_date"
        latest_sync = self._get_latest_sync()
        if latest_sync and latest_sync.get("SynchDate"):
            utc_dt = dt_util.parse_datetime(latest_sync["SynchDate"])
            if utc_dt is not None:
                self._attr_native_value = dt_util.as_local(utc_dt)
            else:
                self._attr_native_value = None
        else:
            self._attr_native_value = None
