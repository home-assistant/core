"""Binary sensor support for the Skybell HD Doorbell."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DOMAIN, SkybellEntity
from .coordinator import SkybellDataUpdateCoordinator

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="button",
        name="Button",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)

# Deprecated in Home Assistant 2022.4
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    async_add_entities(
        SkybellBinarySensor(coordinator, sensor)
        for sensor in BINARY_SENSOR_TYPES
        for coordinator in hass.data[DOMAIN][entry.entry_id].values()
    )


class SkybellBinarySensor(SkybellEntity, BinarySensorEntity):
    """A binary sensor implementation for Skybell devices."""

    coordinator: SkybellDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor for a Skybell device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._event: dict[str, str] = {}
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes."""
        attrs = super().extra_state_attributes
        attrs["event_date"] = self._event.get("createdAt")
        return attrs

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        self._event = (
            self.coordinator.device.latest(
                f"device:sensor:{self.entity_description.key}"
            )
            or {}
        )
        return bool(self._event and self._event.get("id") != self._event.get("id"))
