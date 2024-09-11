"""Support for SLZB-06 sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain

from pysmlight import Sensors

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
from .const import UPTIME_DEVIATION
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
    entry: SmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        chain(
            (SmSensorEntity(coordinator, description) for description in SENSORS),
            (SmUptimeSensorEntity(coordinator, description) for description in UPTIME),
        )
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

    @property
    def native_value(self) -> datetime | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data.sensors)


class SmUptimeSensorEntity(SmSensorEntity):
    """Representation of a slzb uptime sensor."""

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        "Initialize uptime sensor instance."
        super().__init__(coordinator, description)
        self._last_uptime: datetime | None = None

    def get_uptime(self, uptime: float | None) -> datetime | None:
        """Return device uptime or zigbee socket uptime.

        Converts uptime from seconds to a datetime value, allow up to 5
        seconds deviation. This avoids unnecessary updates to sensor state,
        that may be caused by clock jitter.
        """
        if uptime is None:
            # reset to unknown state
            self._last_uptime = None
            return None

        new_uptime = utcnow() - timedelta(seconds=uptime)

        if (
            not self._last_uptime
            or abs(new_uptime - self._last_uptime) > UPTIME_DEVIATION
        ):
            self._last_uptime = new_uptime

        return self._last_uptime

    @property
    def native_value(self) -> datetime | None:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self.coordinator.data.sensors)

        return self.get_uptime(value)
