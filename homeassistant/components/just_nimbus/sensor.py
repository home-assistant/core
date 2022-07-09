"""Support for the CO2signal platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import justnimbus

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import JustNimbusCoordinator
from .const import DOMAIN, VOLUME_FLOW_RATE_LITERS_PER_MINUTE
from .entity import JustNimbusEntity

SCAN_INTERVAL = timedelta(minutes=3)


@dataclass
class JustNimbusEntityDescription(SensorEntityDescription):
    """Provide a description of a JustNimbus sensor."""

    unique_id: str | None = None


SENSOR_TYPES = (
    JustNimbusEntityDescription(
        key="pump_flow",
        name="Pump Flow",
        icon="mdi:pump",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITERS_PER_MINUTE,
        unique_id="jn:pump_flow",
    ),
    JustNimbusEntityDescription(
        key="drink_flow",
        name="Drink Flow",
        icon="mdi:water-pump",
        native_unit_of_measurement=VOLUME_FLOW_RATE_LITERS_PER_MINUTE,
        unique_id="jn:drink_flow",
    ),
    JustNimbusEntityDescription(
        key="pump_pressure",
        name="Pump Pressure",
        icon="mdi:arrow-collapse-vertical",
        native_unit_of_measurement=PRESSURE_BAR,
        device_class=SensorDeviceClass.PRESSURE,
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
        device_class=SensorDeviceClass.DURATION,
        unique_id="jn:pump_hours",
    ),
    JustNimbusEntityDescription(
        key="reservoir_temp",
        name="Reservoir Temperature",
        icon="mdi:thermometer-water",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        unique_id="jn:reservoir_temp",
    ),
    JustNimbusEntityDescription(
        key="reservoir_content",
        name="Reservoir Content",
        icon="mdi:car-coolant-level",
        native_unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:reservoir_content",
    ),
    JustNimbusEntityDescription(
        key="total_saved",
        name="Total Saved",
        icon="mdi:water-opacity",
        native_unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:total_saved",
    ),
    JustNimbusEntityDescription(
        key="total_replenished",
        name="Total Replenished",
        icon="mdi:water",
        native_unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:total_replenished",
    ),
    JustNimbusEntityDescription(
        key="error_code",
        name="Error Code",
        icon="mdi:bug",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="",
        unique_id="jn:error_code",
    ),
    JustNimbusEntityDescription(
        key="totver",
        name="Total Use",
        icon="mdi:chart-donut",
        native_unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:totver",
    ),
    JustNimbusEntityDescription(
        key="reservoir_content_max",
        name="Max Reservoir Content",
        icon="mdi:waves",
        native_unit_of_measurement=VOLUME_LITERS,
        unique_id="jn:reservoir_content_max",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JustNimbus sensor."""
    coordinator: JustNimbusCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JustNimbusSensor(
            client=justnimbus.JustNimbusClient(entry.data[CONF_CLIENT_ID]),
            entry_id=entry.entry_id,
            device_id=entry.data[CONF_CLIENT_ID],
            description=description,
            coordinator=coordinator,
        )
        for description in SENSOR_TYPES
    )


class JustNimbusSensor(
    JustNimbusEntity,
):
    """Implementation of the JustNimbus sensor."""

    def __init__(
        self,
        *,
        client: justnimbus.JustNimbusClient,
        entry_id: str,
        device_id: str,
        description: JustNimbusEntityDescription,
        coordinator: JustNimbusCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(
            client=client,
            entry_id=entry_id,
            device_id=device_id,
            coordinator=coordinator,
        )
        self.client = client
        self._entry_id = entry_id
        self._device_id = device_id
        self._attr_unique_id = f"{entry_id}_{description.unique_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and getattr(self.coordinator.data, self.entity_description.key) is not None
        )

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return getattr(self.coordinator.data, self.entity_description.key)
