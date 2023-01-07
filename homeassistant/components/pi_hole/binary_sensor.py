"""Support for getting status from a Pi-hole system."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hole import Hole

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN as PIHOLE_DOMAIN


@dataclass
class RequiredPiHoleBinaryDescription:
    """Represent the required attributes of the PiHole binary description."""

    state_value: Callable[[Hole], bool]


@dataclass
class PiHoleBinarySensorEntityDescription(
    BinarySensorEntityDescription, RequiredPiHoleBinaryDescription
):
    """Describes PiHole binary sensor entity."""

    extra_value: Callable[[Hole], dict[str, Any] | None] = lambda api: None


BINARY_SENSOR_TYPES: tuple[PiHoleBinarySensorEntityDescription, ...] = (
    PiHoleBinarySensorEntityDescription(
        # Deprecated, scheduled to be removed in 2022.6
        key="core_update_available",
        name="Core Update Available",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.UPDATE,
        extra_value=lambda api: {
            "current_version": api.versions["core_current"],
            "latest_version": api.versions["core_latest"],
        },
        state_value=lambda api: bool(api.versions["core_update"]),
    ),
    PiHoleBinarySensorEntityDescription(
        # Deprecated, scheduled to be removed in 2022.6
        key="web_update_available",
        name="Web Update Available",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.UPDATE,
        extra_value=lambda api: {
            "current_version": api.versions["web_current"],
            "latest_version": api.versions["web_latest"],
        },
        state_value=lambda api: bool(api.versions["web_update"]),
    ),
    PiHoleBinarySensorEntityDescription(
        # Deprecated, scheduled to be removed in 2022.6
        key="ftl_update_available",
        name="FTL Update Available",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.UPDATE,
        extra_value=lambda api: {
            "current_version": api.versions["FTL_current"],
            "latest_version": api.versions["FTL_latest"],
        },
        state_value=lambda api: bool(api.versions["FTL_update"]),
    ),
    PiHoleBinarySensorEntityDescription(
        key="status",
        name="Status",
        icon="mdi:pi-hole",
        state_value=lambda api: bool(api.data.get("status") == "enabled"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pi-hole binary sensor."""
    name = entry.data[CONF_NAME]
    hole_data = hass.data[PIHOLE_DOMAIN][entry.entry_id]

    binary_sensors = [
        PiHoleBinarySensor(
            hole_data[DATA_KEY_API],
            hole_data[DATA_KEY_COORDINATOR],
            name,
            entry.entry_id,
            description,
        )
        for description in BINARY_SENSOR_TYPES
    ]

    async_add_entities(binary_sensors, True)


class PiHoleBinarySensor(PiHoleEntity, BinarySensorEntity):
    """Representation of a Pi-hole binary sensor."""

    entity_description: PiHoleBinarySensorEntityDescription

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        description: PiHoleBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

        if description.key == "status":
            self._attr_name = f"{name}"
        else:
            self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{self._server_unique_id}/{description.name}"

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""

        return self.entity_description.state_value(self.api)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the Pi-hole."""
        return self.entity_description.extra_value(self.api)
