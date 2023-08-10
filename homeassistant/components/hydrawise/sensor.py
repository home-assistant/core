"""Support for Hydrawise sprinkler sensors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, UnitOfTime
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        name="Next Cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="watering_time",
        name="Watering Time",
        icon="mdi:water-pump",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

# Deprecated since Home Assistant 2023.8.0
# Can be removed completely in 2024.2.0
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)

TWO_YEAR_SECONDS = 60 * 60 * 24 * 365 * 2
WATERING_TIME_ICON = "mdi:water-pump"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    # Setup is a noop because we automatically trigger YAML import to config flow.
    return


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hydrawise sensor platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities = [
        HydrawiseSensor(data=zone, coordinator=coordinator, description=description)
        for zone in coordinator.api.relays
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        LOGGER.debug("Updating Hydrawise sensor: %s", self.name)
        relay_data = self.coordinator.api.relays_by_zone_number[self.data["relay"]]
        if self.entity_description.key == "watering_time":
            if relay_data["timestr"] == "Now":
                self._attr_native_value = int(relay_data["run"] / 60)
            else:
                self._attr_native_value = 0
        else:  # _sensor_type == 'next_cycle'
            next_cycle = min(relay_data["time"], TWO_YEAR_SECONDS)
            LOGGER.debug("New cycle time: %s", next_cycle)
            self._attr_native_value = dt_util.utc_from_timestamp(
                dt_util.as_timestamp(dt_util.now()) + next_cycle
            )
        super()._handle_coordinator_update()
