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
    if tank_data.get("DeviceName"):
        return tank_data["DeviceName"]

    owner_info = tank_data.get("Owner")
    if owner_info and owner_info.get("Firstname"):
        return f"Tank for {owner_info['Firstname']}"

    return f"Tank {tank_data.get('Id', 'Unknown')}"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    if coordinator.data:
        for tank_data in coordinator.data:
            entities.append(TankLevelSensor(coordinator, tank_data))
            entities.append(TankBatterySensor(coordinator, tank_data))
            entities.append(TankLastSyncDateSensor(coordinator, tank_data))
            entities.append(TankLastSyncTimeSensor(coordinator, tank_data))
    async_add_entities(entities)


class BaseTankSensor(CoordinatorEntity, SensorEntity):
    """Base class for Rotarex tank sensors."""

    def __init__(self, coordinator, tank_data):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._tank_id = tank_data["Id"]
        self._update_internal_state(tank_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for tank_data in self.coordinator.data:
            if tank_data["Id"] == self._tank_id:
                self._update_internal_state(tank_data)
                self.async_write_ha_state()
                break

    def _update_internal_state(self, tank_data):
        """Update sensor's internal state from tank_data."""
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        tank_data = next(
            (tank for tank in self.coordinator.data if tank["Id"] == self._tank_id),
            None,
        )
        device_name = get_tank_name(tank_data) if tank_data else f"Tank {self._tank_id}"

        return DeviceInfo(
            identifiers={(DOMAIN, self._tank_id)},
            name=device_name,
            manufacturer="Rotarex",
            model="Wave Tank",
        )


class TankLevelSensor(BaseTankSensor):
    """Representation of a Tank Level Sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.VOLUME_STORAGE

    def _update_internal_state(self, tank_data):
        """Update sensor's internal state from tank_data."""
        self._attr_name = f"{get_tank_name(tank_data)} Level"
        self._attr_unique_id = f"rotarex_{self._tank_id}_level"

        latest_sync = (
            max(tank_data["SynchDatas"], key=lambda x: x["SynchDate"])
            if tank_data.get("SynchDatas")
            else None
        )
        if latest_sync:
            self._attr_native_value = latest_sync.get("Level")
            self._attr_extra_state_attributes = {
                "last_synch": latest_sync.get("SynchDate"),
                "temperature": latest_sync.get("Temperature"),
            }
        else:
            self._attr_native_value = None


class TankBatterySensor(BaseTankSensor):
    """Representation of a Tank Battery Sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    def _update_internal_state(self, tank_data):
        """Update sensor's internal state from tank_data."""
        self._attr_name = f"{get_tank_name(tank_data)} Battery"
        self._attr_unique_id = f"rotarex_{self._tank_id}_battery"

        latest_sync = (
            max(tank_data["SynchDatas"], key=lambda x: x["SynchDate"])
            if tank_data.get("SynchDatas")
            else None
        )
        if latest_sync:
            self._attr_native_value = latest_sync.get("Battery")
            self._attr_extra_state_attributes = {
                "last_synch": latest_sync.get("SynchDate")
            }
        else:
            self._attr_native_value = None


class TankLastSyncDateSensor(BaseTankSensor):
    """Representation of a Tank Last Sync Date Sensor."""

    _attr_icon = "mdi:calendar"

    def _update_internal_state(self, tank_data):
        """Update sensor's internal state from tank_data."""
        self._attr_name = f"{get_tank_name(tank_data)} Last Sync Date"
        self._attr_unique_id = f"rotarex_{self._tank_id}_last_sync_date"

        latest_sync = (
            max(tank_data["SynchDatas"], key=lambda x: x["SynchDate"])
            if tank_data.get("SynchDatas")
            else None
        )
        if latest_sync and latest_sync.get("SynchDate"):
            utc_dt = dt_util.parse_datetime(latest_sync["SynchDate"])
            local_dt = dt_util.as_local(utc_dt)
            self._attr_native_value = local_dt.strftime("%d-%m-%Y")
        else:
            self._attr_native_value = None


class TankLastSyncTimeSensor(BaseTankSensor):
    """Representation of a Tank Last Sync Time Sensor."""

    _attr_icon = "mdi:clock-outline"

    def _update_internal_state(self, tank_data):
        """Update sensor's internal state from tank_data."""
        self._attr_name = f"{get_tank_name(tank_data)} Last Sync Time"
        self._attr_unique_id = f"rotarex_{self._tank_id}_last_sync_time"

        latest_sync = (
            max(tank_data["SynchDatas"], key=lambda x: x["SynchDate"])
            if tank_data.get("SynchDatas")
            else None
        )
        if latest_sync and latest_sync.get("SynchDate"):
            utc_dt = dt_util.parse_datetime(latest_sync["SynchDate"])
            local_dt = dt_util.as_local(utc_dt)
            self._attr_native_value = local_dt.strftime("%H:%M:%S")
        else:
            self._attr_native_value = None
