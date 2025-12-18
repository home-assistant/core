from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


def get_tank_name(tank_data: dict) -> str:
    """Generate a name for the tank from the available data."""
    if tank_data and tank_data.get("Name"):
        return tank_data["Name"]
    if tank_data:
        return f"Tank {tank_data.get('Guid', 'Unknown')}"
    return "Unknown Tank"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
    entities = []
    if coordinator.data:
        for tank_data in coordinator.data:
            # Ensure the tank has a Guid before creating sensors
            if tank_data.get("Guid"):
                entities.append(TankLevelSensor(coordinator, tank_data))
                entities.append(TankBatterySensor(coordinator, tank_data))
                entities.append(TankLastSyncDateSensor(coordinator, tank_data))

    async_add_entities(entities)


class BaseTankSensor(CoordinatorEntity, SensorEntity):
    """Base class for Rotarex tank sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, tank_data):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._tank_id = tank_data["Guid"]
        self._update_internal_state(tank_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for tank_data in self.coordinator.data:
            if tank_data.get("Guid") == self._tank_id:
                self._update_internal_state(tank_data)
                self.async_write_ha_state()
                break

    def _update_internal_state(self, tank_data):
        """Update sensor's internal state from tank_data."""
        raise NotImplementedError

    def _get_latest_sync(self):
        """Get the latest sync data for the tank."""
        tank_data = next(
            (
                tank
                for tank in self.coordinator.data
                if tank.get("Guid") == self._tank_id
            ),
            None,
        )
        if tank_data and tank_data.get("SynchDatas"):
            return max(tank_data["SynchDatas"], key=lambda x: x["SynchDate"])
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        tank_data = next(
            (
                tank
                for tank in self.coordinator.data
                if tank.get("Guid") == self._tank_id
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        latest_sync = self._get_latest_sync()
        if not latest_sync:
            return None
        return {
            "last_sync": latest_sync.get("SynchDate"),
            "temperature": latest_sync.get("Temperature"),
        }

    def _update_internal_state(self, tank_data):
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        latest_sync = self._get_latest_sync()
        if not latest_sync:
            return None
        return {
            "last_sync": latest_sync.get("SynchDate"),
        }

    def _update_internal_state(self, tank_data):
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

    def _update_internal_state(self, tank_data):
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
