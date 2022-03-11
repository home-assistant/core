"""Binary sensor support for the Skybell HD Doorbell."""
from __future__ import annotations

from aioskybell.helpers import const as CONST
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
        for coordinator in hass.data[DOMAIN][entry.entry_id]
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
        self._attr_unique_id = f"{coordinator.device.device_id}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict[str, str | int | tuple[str, str]]:
        """Return the state attributes."""
        attrs = super().extra_state_attributes
        if event := self._event.get(CONST.CREATED_AT):
            attrs["event_date"] = event
        return attrs

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        event = self.coordinator.device.latest(f"{self.entity_description.key}")
        result = bool(event.get(CONST.ID) != self._event.get(CONST.ID))
        self._event = event
        return result
