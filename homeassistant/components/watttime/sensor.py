"""Support for WattTime sensors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, MASS_POUNDS, PERCENTAGE
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
    CONF_SHOW_ON_MAP,
    DOMAIN,
)

ATTR_BALANCING_AUTHORITY = "balancing_authority"

SENSOR_TYPE_REALTIME_EMISSIONS_MOER = "moer"
SENSOR_TYPE_REALTIME_EMISSIONS_PERCENT = "percent"


REALTIME_EMISSIONS_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_TYPE_REALTIME_EMISSIONS_MOER,
        name="Marginal Operating Emissions Rate",
        icon="mdi:blur",
        native_unit_of_measurement=f"{MASS_POUNDS} CO2/MWh",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_REALTIME_EMISSIONS_PERCENT,
        name="Relative Marginal Emissions Intensity",
        icon="mdi:blur",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WattTime sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RealtimeEmissionsSensor(coordinator, entry, description)
            for description in REALTIME_EMISSIONS_SENSOR_DESCRIPTIONS
            if description.key in coordinator.data
        ]
    )


class RealtimeEmissionsSensor(CoordinatorEntity, SensorEntity):
    """Define a realtime emissions sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_name = (
            f"{description.name} ({entry.data[CONF_BALANCING_AUTHORITY_ABBREV]})"
        )
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._entry = entry
        self.entity_description = description

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {
            ATTR_BALANCING_AUTHORITY: self._entry.data[CONF_BALANCING_AUTHORITY],
        }

        # Displaying the geography on the map relies upon putting the latitude/longitude
        # in the entity attributes with "latitude" and "longitude" as the keys.
        # Conversely, we can hide the location on the map by using other keys, like
        # "lati" and "long".
        if self._entry.options.get(CONF_SHOW_ON_MAP) is not False:
            attrs[ATTR_LATITUDE] = self._entry.data[ATTR_LATITUDE]
            attrs[ATTR_LONGITUDE] = self._entry.data[ATTR_LONGITUDE]
        else:
            attrs["lati"] = self._entry.data[ATTR_LATITUDE]
            attrs["long"] = self._entry.data[ATTR_LONGITUDE]

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return cast(StateType, self.coordinator.data[self.entity_description.key])
