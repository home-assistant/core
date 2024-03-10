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
    coordinator: TrestDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions = [
        # SensorEntityDescription(
        #    key="id",
        #    name="ID",
        # ),
        # SensorEntityDescription(
        #    key="serial_number",
        #    name="Serial Number",
        # ),
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
        TrestSolarControllerSensor(coordinator, description)
        for description in descriptions
    ]

    async_add_entities(entities)


class TrestSolarControllerSensor(CoordinatorEntity[TrestDataCoordinator], SensorEntity):
    """The sensor for Trest Solar Controller."""

    def __init__(
        self, coordinator: TrestDataCoordinator, description: SensorEntityDescription
    ) -> None:
        """TrestSolarControllerSensor constructor."""
        super().__init__(coordinator)
        self.description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""

        if self.description.key == "timestamp":
            timestamp_str = getattr(self.coordinator.data, self.description.key)
            return datetime.fromisoformat(timestamp_str)

        if hasattr(self.coordinator.data, self.description.key):
            return getattr(self.coordinator.data, self.description.key)

        return None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return f"{self.description.name}"

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this device."""
        return self.description.device_class

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity."""
        return self.description.state_class
