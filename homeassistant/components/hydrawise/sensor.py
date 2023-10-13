"""Support for Hydrawise sprinkler sensors."""
from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, UnitOfTime
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NEXT_CYCLE_SUSPENDED
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        translation_key="next_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="watering_time",
        translation_key="watering_time",
        icon="mdi:water-pump",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

# Deprecated since Home Assistant 2023.10.0
# Can be removed completely in 2024.4.0
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)

WATERING_TIME_ICON = "mdi:water-pump"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    # We don't need to trigger import flow from here as it's triggered from `__init__.py`
    return  # pragma: no cover


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

    def _update_attrs(self) -> None:
        """Update state attributes."""
        relay_data = self.coordinator.api.relays_by_zone_number[self.data["relay"]]
        if self.entity_description.key == "watering_time":
            if relay_data["timestr"] == "Now":
                self._attr_native_value = int(relay_data["run"] / 60)
            else:
                self._attr_native_value = 0
        elif self.entity_description.key == "next_cycle":
            if (next_cycle := relay_data["time"]) == NEXT_CYCLE_SUSPENDED:
                # When the zone is suspended, we can't calculate a next cycle time.
                self._attr_native_value = None
            else:
                next_cycle_delta = timedelta(seconds=next_cycle)
                self._attr_native_value = dt_util.utcnow() + next_cycle_delta
