"""Switch entities for the Marketplace."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .base import MarketplaceConfigEntry, MarketplaceManager
from .entity import RepositoryEntity
from .repositories.base import Repository

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarketplaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup switch platform."""
    marketplace = entry.runtime_data
    async_add_entities(
        RepositoryPreReleaseSwitchEntity(marketplace=marketplace, repository=repository)
        for repository in marketplace.repositories.list_installed
    )


class RepositoryPreReleaseSwitchEntity(RepositoryEntity, SwitchEntity):
    """Pre-release switch entity for an installed repository."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "pre-release"

    def __init__(self, marketplace: MarketplaceManager, repository: Repository) -> None:
        """Initialize the repository pre-release switch."""
        super().__init__(marketplace, repository)
        self._attr_entity_registry_enabled_default = self.repository.data.show_beta

    @property
    @override
    def is_on(self) -> bool:
        """Return if the pre-release option is enabled for the repository."""
        return self.repository.data.show_beta

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._handle_change(value=True)

    @override
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

        # Write the Marketplace data and update the entity state
        await self.marketplace.data.async_write()
        self.async_write_ha_state()
