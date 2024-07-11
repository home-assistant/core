"""Support for SLZB-06 sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import LOGGER, SCAN_INTERVAL, SMLIGHT_SLZB_REBOOT_EVENT
from .coordinator import SmData, SmDataUpdateCoordinator
from .entity import SmEntity

UPTIME_DEVIATION = 5  # seconds


@dataclass(frozen=True, kw_only=True)
class SmSensorEntityDescription(SensorEntityDescription):
    """Class describing SMLIGHT sensor entities."""

    value_fn: Callable[[SmData], float | None] = lambda _: None


SENSORS = [
    SmSensorEntityDescription(
        key="esp32_temperature",
        translation_key="core_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x.sensors.esp32_temp,
    ),
    SmSensorEntityDescription(
        key="zb_temperature",
        translation_key="zigbee_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x.sensors.zb_temp,
    ),
    SmSensorEntityDescription(
        key="core_uptime",
        translation_key="core_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.sensors.uptime,
    ),
    SmSensorEntityDescription(
        key="socket_uptime",
        translation_key="socket_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.sensors.socket_uptime,
    ),
    SmSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.sensors.ram_usage,
    ),
    SmSensorEntityDescription(
        key="fs_usage",
        translation_key="fs_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.sensors.fs_used,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator: SmDataUpdateCoordinator = entry.runtime_data

    sensors = [SmSensorEntity(coordinator, description) for description in SENSORS]
    async_add_entities(sensors)


class SmSensorEntity(SmEntity, SensorEntity):
    """Representation of a slzb sensor."""

    # entity_description: SmSensorEntityDescription

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        """Initiate slzb sensor."""
        super().__init__(coordinator)
        # CoordinatorEntity.__init__(self, coordinator)

        self.entity_description: SmSensorEntityDescription = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._last_uptime: datetime | None = None

    def get_device_uptime(self, uptime: float | None) -> datetime:
        """Return device uptime string, tolerate up to 5 seconds deviation."""
        uptime = 0 if uptime is None else uptime
        delta = timedelta(seconds=uptime)
        last_uptime = self._last_uptime

        if "core_uptime" in self.entity_description.key and delta <= SCAN_INTERVAL:
            self.coordinator.hass.bus.async_fire(
                SMLIGHT_SLZB_REBOOT_EVENT,
                {
                    "device_id": self.coordinator.unique_id,
                    "uptime": delta.total_seconds(),
                },
            )
            LOGGER.debug("SLZB device reboot detected")

        delta_uptime = utcnow() - delta

        if (
            not last_uptime
            or abs((delta_uptime - last_uptime).total_seconds()) > UPTIME_DEVIATION
        ):
            return delta_uptime

        return last_uptime

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self.coordinator.data)

        if "uptime" in self.entity_description.key:
            if value:
                self._last_uptime = self.get_device_uptime(value)
            return self._last_uptime

        return value
