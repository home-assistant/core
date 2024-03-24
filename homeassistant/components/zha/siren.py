"""Support for ZHA sirens."""

from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import EntityData, get_zha_data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation siren from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.SENSOR, [])
    async_add_entities(entities_to_create)


class ZHASiren(ZHAEntity, SirenEntity):
    """Representation of a ZHA siren."""

    _attr_name: str = "Siren"

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA siren."""
        super().__init__(entity_data, **kwargs)
        self._attr_supported_features = SirenEntityFeature(
            self.entity_data.entity._attr_supported_features.value
        )

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.entity_data.entity.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on siren."""
        await self.entity_data.entity.async_turn_on(**kwargs)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off siren."""
        await self.entity_data.entity.async_turn_off(**kwargs)
        self.async_write_ha_state()
