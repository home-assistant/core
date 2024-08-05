"""Sensor platform for JVC Projector integration."""

from __future__ import annotations

from jvcprojector import const

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JvcProjectorDataUpdateCoordinator
from .const import DOMAIN
from .entity import JvcProjectorEntity

JVC_SENSORS = (
    SensorEntityDescription(
        key="power",
        translation_key="jvc_power_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.STANDBY,
            const.ON,
            const.WARMING,
            const.COOLING,
            const.ERROR,
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator: JvcProjectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        JvcSensor(coordinator, description) for description in JVC_SENSORS
    )


class JvcSensor(JvcProjectorEntity, SensorEntity):
    """The entity class for JVC Projector integration."""

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the native value."""
        return self.coordinator.data[self.entity_description.key]
