"""Support for the CO2signal platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import justnimbus

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRESSURE_BAR, TEMP_CELSIUS, VOLUME_LITERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import JustNimbusCoordinator
from .const import DOMAIN, VOLUME_FLOW_RATE_LITERS_PER_MINUTE

SCAN_INTERVAL = timedelta(minutes=3)


@dataclass
class JustNimbusEntityDescription:
    """Provide a description of a CO2 sensor."""

    key: str
    name: str
    icon: str
    unit_of_measurement: str | None = None
    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None
    entity_registry_enabled_default: bool = True


SENSOR_TYPES: tuple[JustNimbusEntityDescription, ...] = (
    JustNimbusEntityDescription(
        key="pump_flow",
        name="Pump Flow",
        icon="mdi:pump",
        unit_of_measurement=VOLUME_FLOW_RATE_LITERS_PER_MINUTE,
        unique_id="jn:pump_flow",
    ),
    JustNimbusEntityDescription(
        key="drink_flow",
        name="Drink Flow",
        icon="mdi:water-pump",
        unit_of_measurement=VOLUME_FLOW_RATE_LITERS_PER_MINUTE,
        unique_id="jn:drink_flow",
    ),
    JustNimbusEntityDescription(
        key="pump_pressure",
        name="Pump Pressure",
        icon="mdi:arrow-collapse-vertical",
        unit_of_measurement=PRESSURE_BAR,
        unique_id="jn:pump_pressure",
    ),
    JustNimbusEntityDescription(
        key="pump_starts",
        name="Pump Starts",
        icon="mdi:restart",
        unique_id="jn:pump_starts",
    ),
    JustNimbusEntityDescription(
        key="pump_hours",
        name="Pump Hours",
        icon="mdi:clock",
        unique_id="jn:pump_hours",
    ),
    JustNimbusEntityDescription(
        key="reservoir_temp",
        name="Reservoir Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        unique_id="jn:reservoir_temp",
    ),
    JustNimbusEntityDescription(
        key="reservoir_content",
        name="Reservoir Content",
        icon="mdi:car-coolant-level",
        unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:reservoir_content",
    ),
    JustNimbusEntityDescription(
        key="total_saved",
        name="Total Saved",
        icon="mdi:water-opacity",
        unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:total_saved",
    ),
    JustNimbusEntityDescription(
        key="total_replenished",
        name="Total Replenished",
        icon="mdi:water",
        unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:total_replenished",
    ),
    JustNimbusEntityDescription(
        key="error_code",
        name="Error Code",
        icon="mdi:bug",
        entity_registry_enabled_default=False,
        unit_of_measurement="",
        unique_id="jn:error_code",
    ),
    JustNimbusEntityDescription(
        key="totver",
        name="Total Use",
        icon="mdi:chart-donut",
        unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:totver",
    ),
    JustNimbusEntityDescription(
        key="reservoir_content_max",
        name="Max Reservoir Content",
        icon="mdi:thermometer",
        unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:reservoir_content_max",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JustNimbus sensor."""
    coordinator: JustNimbusCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JustNimbusSensor(coordinator, description) for description in SENSOR_TYPES
    )


class JustNimbusSensor(
    update_coordinator.CoordinatorEntity[justnimbus.JustNimbusModel], SensorEntity
):
    """Implementation of the JustNimbus sensor."""

    def __init__(
        self,
        coordinator: JustNimbusCoordinator,
        description: JustNimbusEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._description = description

        name = description.name

        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name="Just Nimbus",
        )
        self._attr_unique_id = description.unique_id
        self._attr_icon = description.icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and getattr(self.coordinator.data, self._description.key) is not None
        )

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return getattr(self.coordinator.data, self._description.key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._attr_unit_of_measurement
