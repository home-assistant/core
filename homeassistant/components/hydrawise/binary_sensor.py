"""Support for Hydrawise sprinkler binary sensors."""
from __future__ import annotations

from pydrawise.schema import Zone
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

BINARY_SENSOR_STATUS = BinarySensorEntityDescription(
    key="status",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_watering",
        translation_key="watering",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)

BINARY_SENSOR_KEYS: list[str] = [
    desc.key for desc in (BINARY_SENSOR_STATUS, *BINARY_SENSOR_TYPES)
]

# Deprecated since Home Assistant 2023.10.0
# Can be removed completely in 2024.4.0
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=BINARY_SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSOR_KEYS)]
        )
    }
)


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
    """Set up the Hydrawise binary_sensor platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities = []
    for controller in coordinator.data.controllers.values():
        entities.append(
            HydrawiseBinarySensor(coordinator, BINARY_SENSOR_STATUS, controller)
        )
        for zone in controller.zones:
            for description in BINARY_SENSOR_TYPES:
                entities.append(
                    HydrawiseBinarySensor(coordinator, description, controller, zone)
                )
    async_add_entities(entities)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    def _update_attrs(self) -> None:
        """Update state attributes."""
        if self.entity_description.key == "status":
            self._attr_is_on = self.coordinator.last_update_success
        elif self.entity_description.key == "is_watering":
            zone: Zone = self.zone
            self._attr_is_on = zone.scheduled_runs.current_run is not None
