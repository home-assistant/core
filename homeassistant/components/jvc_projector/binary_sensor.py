"""Binary Sensor platform for JVC Projector integration."""

from __future__ import annotations

from jvcprojector import const

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity

ON_STATUS = (const.ON, const.WARMING)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities([JvcBinarySensor(coordinator)])


class JvcBinarySensor(JvcProjectorEntity, BinarySensorEntity):
    """The entity class for JVC Projector Binary Sensor."""

    _attr_translation_key = "jvc_power"

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.mac}_power"

    @property
    def is_on(self) -> bool:
        """Return true if the JVC is on."""
        return self.coordinator.data["power"] in ON_STATUS
