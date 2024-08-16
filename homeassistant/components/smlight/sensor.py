"""Support for SLZB-06 sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pysmlight.web import Sensors

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import SmConfigEntry
from .const import LOGGER, SCAN_INTERVAL, SMLIGHT_SLZB_REBOOT_EVENT, UPTIME_DEVIATION
from .coordinator import SmDataUpdateCoordinator
from .entity import SmEntity


@dataclass(frozen=True, kw_only=True)
class SmSensorEntityDescription(SensorEntityDescription):
    """Class describing SMLIGHT sensor entities."""

    entity_category = EntityCategory.DIAGNOSTIC
    value_fn: Callable[[Sensors], float | None]


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
        value_fn=lambda x: x.socket_uptime if x.socket_uptime > 0 else None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SmSensorEntity(coordinator, description) for description in SENSORS
    )


class SmSensorEntity(SmEntity, SensorEntity):
    """Representation of a slzb sensor."""

    entity_description: SmSensorEntityDescription

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        """Initiate slzb sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._last_uptime: datetime | None = None

    def get_uptime(self, uptime: float | None) -> datetime | None:
        """Return device or zigbee socket uptime.

        Converts uptime from seconds to a datetime value, allow up to 5
        seconds deviation. Fire a reboot event if device uptime has reset
        since last run.
        """
        if uptime is None:
            # reset to unknown state
            self._last_uptime = None
            return None

        delta = timedelta(seconds=uptime)

        if "core_uptime" in self.entity_description.key and delta <= SCAN_INTERVAL:
            self.fire_reboot_event()

        new_uptime = utcnow() - delta

        if (
            not self._last_uptime
            or abs(new_uptime - self._last_uptime) > UPTIME_DEVIATION
        ):
            self._last_uptime = new_uptime

        return self._last_uptime

    def fire_reboot_event(self):
        """Fire reboot event."""
        self.coordinator.hass.bus.async_fire(
            SMLIGHT_SLZB_REBOOT_EVENT,
            {
                "device_id": self.coordinator.unique_id,
                "host": self.coordinator.hostname,
            },
        )
        LOGGER.debug("SLZB device reboot detected")

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self.coordinator.data.sensors)

        if "uptime" in self.entity_description.key:
            self._last_uptime = self.get_uptime(value)
            return self._last_uptime

        return value
