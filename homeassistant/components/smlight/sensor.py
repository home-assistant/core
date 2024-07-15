"""Support for SLZB-06 sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain

from pysmlight.web import Sensors

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
from .coordinator import SmDataUpdateCoordinator
from .entity import SmEntity


@dataclass(frozen=True, kw_only=True)
class SmSensorEntityDescription(SensorEntityDescription):
    """Class describing SMLIGHT sensor entities."""

    entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    value_fn: Callable[[Sensors], float | None] = lambda _: None


SENSORS = [
    SmSensorEntityDescription(
        key="core_temperature",
        translation_key="core_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x.esp32_temp,
    ),
    SmSensorEntityDescription(
        key="zigbee_temperature",
        translation_key="zigbee_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x.zb_temp,
    ),
    SmSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.ram_usage,
    ),
    SmSensorEntityDescription(
        key="fs_usage",
        translation_key="fs_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.fs_used,
    ),
]
UPTIME = [
    SmSensorEntityDescription(
        key="core_uptime",
        translation_key="core_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.uptime,
    ),
    SmSensorEntityDescription(
        key="socket_uptime",
        translation_key="socket_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.socket_uptime,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator: SmDataUpdateCoordinator = entry.runtime_data

    async_add_entities(
        chain(
            (SmSensorEntity(coordinator, description) for description in SENSORS),
            (SmUptimeSensorEntity(coordinator, description) for description in UPTIME),
        )
    )


class SmSensorEntity(SmEntity, SensorEntity):
    """Representation of a slzb sensor."""

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        """Initiate slzb sensor."""
        super().__init__(coordinator)

        self.entity_description: SmSensorEntityDescription = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data.sensors)


class SmUptimeSensorEntity(SmSensorEntity):
    """Helper class to process uptime sensors."""

    MAX_DEVIATION = 5  # seconds

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        "Initialize uptime sensor instance."
        super().__init__(coordinator, description)
        self.last_uptime: datetime | None = None

    def get_uptime(self, uptime: float | None) -> datetime | None:
        """Return device uptime, tolerate up to 5 seconds deviation."""
        if uptime == 0 or uptime is None:
            self.last_uptime = None
            return None

        delta = timedelta(seconds=uptime)

        if "core_uptime" in self.entity_description.key and delta <= SCAN_INTERVAL:
            self.coordinator.hass.bus.async_fire(
                SMLIGHT_SLZB_REBOOT_EVENT,
                {
                    "device_id": self.coordinator.unique_id,
                    "host": self.coordinator.hostname,
                },
            )
            LOGGER.debug("SLZB device reboot detected")

        delta_uptime = utcnow() - delta

        if (
            not self.last_uptime
            or abs((delta_uptime - self.last_uptime).total_seconds())
            > SmUptimeSensorEntity.MAX_DEVIATION
        ):
            self.last_uptime = delta_uptime

        return self.last_uptime

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self.coordinator.data.sensors)

        return self.get_uptime(value)
