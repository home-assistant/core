"""Switch entities for HACS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import HacsBase
from .const import DOMAIN
from .entity import HacsRepositoryEntity
from .repositories.base import HacsRepository


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup switch platform."""
    hacs: HacsBase = hass.data[DOMAIN]
    async_add_entities(
        HacsRepositoryPreReleaseSwitchEntity(hacs=hacs, repository=repository)
        for repository in hacs.repositories.list_downloaded
    )


class HacsRepositoryPreReleaseSwitchEntity(HacsRepositoryEntity, SwitchEntity):
    """Pre-release switch entities for repositories downloaded with HACS."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "pre-release"

    def __init__(self, hacs: HacsBase, repository: HacsRepository) -> None:
        """Initialize the repository pre-release switch."""
        super().__init__(hacs, repository)
        self._attr_entity_registry_enabled_default = self.repository.data.show_beta

    @property
    def is_on(self) -> bool:
        """Return if the pre-release option is enabled for the repository."""
        return self.repository.data.show_beta

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._handle_change(value=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._handle_change(value=False)

    async def _handle_change(self, value: bool) -> None:
        """Handle attribute value changes."""
        self.repository.data.show_beta = value

        # As this value is directly affecting what data points is in use by other entities
        # we need to update all entities to reflect the change
        # Do force an update of the entities we need to clear the last fetched data
        # since that is used to limit state updates
        # Once we have signaled the update we can restore the last fetched data
        _last_fetch = self.repository.data.last_fetched
        self.repository.data.last_fetched = None
        self.coordinator.async_update_listeners()
        self.repository.data.last_fetched = _last_fetch  # Restore last fetched

        # Write the HACS data and update the entity state
        await self.hacs.data.async_write()
        self.async_write_ha_state()
