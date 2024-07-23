"""Class representing each Trest Solar Controller device."""
from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TrestDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a Trest Solar Controller entry."""
    runtime_data = hass.data["runtime_data"].get(entry.entry_id)
    if runtime_data is None:
        return

    coordinator: TrestDataCoordinator = runtime_data.coordinator
    descriptions = [
        SensorEntityDescription(
            key="battery_discharge",
            name="Battery Discharge",
        ),
        SensorEntityDescription(
            key="battery_charge",
            name="Battery Charge",
        ),
        SensorEntityDescription(
            key="battery_capacity",
            name="Battery Capacity",
        ),
        SensorEntityDescription(
            key="battery_stored_power",
            name="Battery Stored Power",
        ),
        SensorEntityDescription(
            key="total_load_active_power",
            name="Total Load Active Power",
        ),
        SensorEntityDescription(
            key="realtime_solar",
            name="Realtime Solar",
        ),
        SensorEntityDescription(
            key="timestamp",
            name="Timestamp",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        SensorEntityDescription(
            key="solar_profile",
            name="Solar Profile",
        ),
        SensorEntityDescription(
            key="daily_yeild",
            name="Daily Yield",
        ),
    ]

    entities = [
        TrestSolarControllerSensor(coordinator, entry.entry_id, description)
        for description in descriptions
    ]

    async_add_entities(entities)


class TrestSolarControllerSensor(CoordinatorEntity[TrestDataCoordinator], SensorEntity):
    """The sensor for Trest Solar Controller."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: TrestDataCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """TrestSolarControllerSensor constructor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}.{description.key}"
        self._attr_device_info = DeviceInfo(
            name="Trest Solar Controller",
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""

        if self.entity_description.key == "timestamp":
            timestamp_str = getattr(self.coordinator.data, self.entity_description.key)
            return datetime.fromisoformat(timestamp_str)

        if hasattr(self.coordinator.data, self.entity_description.key):
            return getattr(self.coordinator.data, self.entity_description.key)

        return None
