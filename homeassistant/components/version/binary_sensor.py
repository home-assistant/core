"""Binary sensor platform for Version."""

from __future__ import annotations

from awesomeversion import AwesomeVersion

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SOURCE, DEFAULT_NAME, DOMAIN
from .coordinator import VersionDataUpdateCoordinator
from .entity import VersionEntity

HA_VERSION_OBJECT = AwesomeVersion(HA_VERSION)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up version binary_sensors."""
    coordinator: VersionDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    if (source := config_entry.data[CONF_SOURCE]) == "local":
        return

    if (entity_name := config_entry.data[CONF_NAME]) == DEFAULT_NAME:
        entity_name = config_entry.title

    entities: list[VersionBinarySensor] = [
        VersionBinarySensor(
            coordinator=coordinator,
            entity_description=BinarySensorEntityDescription(
                key=str(source),
                name=f"{entity_name} Update Available",
                device_class=BinarySensorDeviceClass.UPDATE,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        )
    ]

    async_add_entities(entities)


class VersionBinarySensor(VersionEntity, BinarySensorEntity):
    """Binary sensor for version entities."""

    entity_description: BinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        version = self.coordinator.version
        return version is not None and (version > HA_VERSION_OBJECT)
