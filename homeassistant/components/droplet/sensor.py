"""Support for Droplet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pydroplet.droplet import Droplet

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_CURRENT_FLOW_RATE,
    KEY_SERVER_CONNECTIVITY,
    KEY_SIGNAL_QUALITY,
    KEY_VOLUME,
)
from .coordinator import DropletConfigEntry, DropletDataCoordinator

ML_L_CONVERSION = 1000


@dataclass(kw_only=True, frozen=True)
class DropletSensorEntityDescription(SensorEntityDescription):
    """Describes Droplet sensor entity."""

    value_fn: Callable[[Droplet], float | str | None]
    last_reset_fn: Callable[[Droplet], datetime | None] = lambda _: None


SENSORS: list[DropletSensorEntityDescription] = [
    DropletSensorEntityDescription(
        key=KEY_CURRENT_FLOW_RATE,
        translation_key=KEY_CURRENT_FLOW_RATE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.get_flow_rate(),
    ),
    DropletSensorEntityDescription(
        key=KEY_VOLUME,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda device: device.get_volume_delta() / ML_L_CONVERSION,
        last_reset_fn=lambda device: device.get_volume_last_fetched(),
    ),
    DropletSensorEntityDescription(
        key=KEY_SERVER_CONNECTIVITY,
        translation_key=KEY_SERVER_CONNECTIVITY,
        device_class=SensorDeviceClass.ENUM,
        options=["connected", "connecting", "disconnected"],
        value_fn=lambda device: device.get_server_status(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DropletSensorEntityDescription(
        key=KEY_SIGNAL_QUALITY,
        translation_key=KEY_SIGNAL_QUALITY,
        device_class=SensorDeviceClass.ENUM,
        options=["no_signal", "weak_signal", "strong_signal"],
        value_fn=lambda device: device.get_signal_quality(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DropletConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Droplet sensors from config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities([DropletSensor(coordinator, sensor) for sensor in SENSORS])


class DropletSensor(CoordinatorEntity[DropletDataCoordinator], SensorEntity):
    """Representation of a Droplet."""

    entity_description: DropletSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DropletDataCoordinator,
        entity_description: DropletSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer=self.coordinator.droplet.get_manufacturer(),
            model=self.coordinator.droplet.get_model(),
            sw_version=self.coordinator.droplet.get_fw_version(),
            serial_number=self.coordinator.droplet.get_sn(),
        )

    @property
    def available(self) -> bool:
        """Get Droplet's availability."""
        return self.coordinator.get_availability()

    @property
    def native_value(self) -> float | str | None:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.droplet)

    @property
    def last_reset(self) -> datetime | None:
        """Return the last reset of the sensor, if applicable."""
        return self.entity_description.last_reset_fn(self.coordinator.droplet)
