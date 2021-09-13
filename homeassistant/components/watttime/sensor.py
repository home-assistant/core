"""Support for WattTime sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_BALANCING_AUTHORITY,
    CONF_BALANCING_AUTHORITY_ABBREV,
    DATA_COORDINATOR,
    DOMAIN,
)

ATTR_BALANCING_AUTHORITY = "balancing_authority"

DEFAULT_ATTRIBUTION = "Pickup data provided by WattTime"

SENSOR_TYPE_REALTIME_EMISSIONS_MOER = "realtime_emissions_moer"
SENSOR_TYPE_REALTIME_EMISSIONS_PERCENT = "realtime_emissions_percent"


@dataclass
class RealtimeEmissionsSensorDescriptionMixin:
    """Define an entity description mixin for realtime emissions sensors."""

    data_key: str


@dataclass
class RealtimeEmissionsSensorEntityDescription(
    SensorEntityDescription, RealtimeEmissionsSensorDescriptionMixin
):
    """Describe a realtime emissions sensor."""


REALTIME_EMISSIONS_SENSOR_DESCRIPTIONS = (
    RealtimeEmissionsSensorEntityDescription(
        key=SENSOR_TYPE_REALTIME_EMISSIONS_MOER,
        name="Marginal Operating Emissions Rate",
        icon="mdi:blur",
        native_unit_of_measurement="lbs CO2/MWh",
        state_class=STATE_CLASS_MEASUREMENT,
        data_key="moer",
    ),
    RealtimeEmissionsSensorEntityDescription(
        key=SENSOR_TYPE_REALTIME_EMISSIONS_PERCENT,
        name="Relative Marginal Emissions Intensity",
        icon="mdi:blur",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        data_key="percent",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WattTime sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]
    async_add_entities(
        [
            RealtimeEmissionsSensor(coordinator, description)
            for description in REALTIME_EMISSIONS_SENSOR_DESCRIPTIONS
            if description.data_key in coordinator.data
        ]
    )


class RealtimeEmissionsSensor(CoordinatorEntity, SensorEntity):
    """Define a realtime emissions sensor."""

    entity_description: RealtimeEmissionsSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: RealtimeEmissionsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        if TYPE_CHECKING:
            assert coordinator.config_entry

        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_BALANCING_AUTHORITY: coordinator.config_entry.data[
                CONF_BALANCING_AUTHORITY
            ],
            ATTR_LATITUDE: coordinator.config_entry.data[ATTR_LATITUDE],
            ATTR_LONGITUDE: coordinator.config_entry.data[ATTR_LONGITUDE],
        }
        self._attr_name = f"{description.name} ({coordinator.config_entry.data[CONF_BALANCING_AUTHORITY_ABBREV]})"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        self._attr_native_value = self.coordinator.data[
            self.entity_description.data_key
        ]
