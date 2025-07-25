"""Support for Droplet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

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
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEVICE_NAME,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SERIAL,
    CONF_SW,
    DOMAIN,
    KEY_CURRENT_FLOW_RATE,
    KEY_SERVER_CONNECTIVITY,
    KEY_SIGNAL_QUALITY,
    KEY_VOLUME,
    AccumulatedVolume,
)
from .coordinator import DropletConfigEntry, DropletDataCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class DropletSensorEntityDescription(SensorEntityDescription):
    """Describes Droplet sensor entity."""

    value_fn: Callable[[DropletDataCoordinator], float | str]


SENSORS: list[DropletSensorEntityDescription] = [
    DropletSensorEntityDescription(
        key=KEY_CURRENT_FLOW_RATE,
        translation_key=KEY_CURRENT_FLOW_RATE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        value_fn=lambda device: device.get_flow_rate(),
    ),
    DropletSensorEntityDescription(
        key=KEY_VOLUME,
        translation_key=KEY_VOLUME,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL,
        has_entity_name=True,
        value_fn=lambda device: device.get_volume_delta(),
    ),
    DropletSensorEntityDescription(
        key=AccumulatedVolume.DAILY,
        translation_key=AccumulatedVolume.DAILY,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_entity_name=True,
        value_fn=lambda device: device.get_daily_volume(),
    ),
    DropletSensorEntityDescription(
        key=AccumulatedVolume.WEEKLY,
        translation_key=AccumulatedVolume.WEEKLY,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_entity_name=True,
        value_fn=lambda device: device.get_weekly_volume(),
    ),
    DropletSensorEntityDescription(
        key=AccumulatedVolume.MONTHLY,
        translation_key=AccumulatedVolume.MONTHLY,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        has_entity_name=True,
        value_fn=lambda device: device.get_monthly_volume(),
    ),
    DropletSensorEntityDescription(
        key=KEY_SERVER_CONNECTIVITY,
        translation_key=KEY_SERVER_CONNECTIVITY,
        device_class=SensorDeviceClass.ENUM,
        options=["Connected", "Connecting", "Disconnected"],
        has_entity_name=True,
        value_fn=lambda device: device.get_server_status(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DropletSensorEntityDescription(
        key=KEY_SIGNAL_QUALITY,
        translation_key=KEY_SIGNAL_QUALITY,
        device_class=SensorDeviceClass.ENUM,
        options=["No Signal", "Weak Signal", "Strong Signal"],
        has_entity_name=True,
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
    _LOGGER.info(
        "Set up sensor for device %s with entry_id is %s",
        config_entry.unique_id,
        config_entry.entry_id,
    )

    coordinator = config_entry.runtime_data
    for sensor in SENSORS:
        async_add_entities([DropletSensor(coordinator, sensor)])


class DropletSensor(CoordinatorEntity[DropletDataCoordinator], SensorEntity):
    """Representation of a Droplet."""

    entity_description: DropletSensorEntityDescription

    def __init__(
        self,
        coordinator: DropletDataCoordinator,
        entity_description: DropletSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{entity_description.key}_{unique_id}"

        entry_data = coordinator.config_entry.data
        if unique_id is not None:
            self._attr_device_info = DeviceInfo(
                manufacturer=entry_data[CONF_MANUFACTURER],
                model=entry_data[CONF_MODEL],
                name=entry_data[CONF_DEVICE_NAME],
                identifiers={(DOMAIN, unique_id)},
                sw_version=entry_data[CONF_SW],
                serial_number=entry_data[CONF_SERIAL],
            )

    @property
    def available(self) -> bool:
        """Get Droplet's availability."""
        return self.coordinator.get_availability()

    @property
    def native_value(self) -> float | str | None:
        """Return the value reported by the sensor."""
        if self.entity_description.key == KEY_VOLUME:
            self._attr_last_reset = dt_util.now()
        return self.entity_description.value_fn(self.coordinator)
