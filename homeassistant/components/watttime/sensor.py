"""Support for WattTime sensors."""
from __future__ import annotations

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
    MASS_POUNDS,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
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

SENSOR_TYPE_REALTIME_EMISSIONS_MOER = "moer"
SENSOR_TYPE_REALTIME_EMISSIONS_PERCENT = "percent"


REALTIME_EMISSIONS_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_REALTIME_EMISSIONS_MOER,
        name="Marginal Operating Emissions Rate",
        icon="mdi:blur",
        native_unit_of_measurement=f"{MASS_POUNDS} CO2/MWh",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_REALTIME_EMISSIONS_PERCENT,
        name="Relative Marginal Emissions Intensity",
        icon="mdi:blur",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WattTime sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            RealtimeEmissionsSensor(coordinator, description)
            for description in REALTIME_EMISSIONS_SENSOR_DESCRIPTIONS
            if description.key in coordinator.data
        ]
    )


class RealtimeEmissionsSensor(CoordinatorEntity, SensorEntity):
    """Define a realtime emissions sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
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

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self.entity_description.key]
