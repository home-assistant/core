"""Base entities for the Marketplace."""

from typing import TYPE_CHECKING, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import BaseCoordinatorEntity

from .const import DOMAIN
from .coordinator import StoreUpdateCoordinator

if TYPE_CHECKING:
    from .base import StoreManager
    from .repositories.base import Repository


class StoreEntity(Entity):
    """Base entity for the Marketplace."""

    repository: Repository
    _attr_should_poll = False

    def __init__(self, store: StoreManager) -> None:
        """Initialize."""
        self.store = store


class RepositoryEntity(BaseCoordinatorEntity[StoreUpdateCoordinator], StoreEntity):
    """Base repository entity."""

    def __init__(
        self,
        store: StoreManager,
        repository: Repository,
    ) -> None:
        """Initialize."""
        BaseCoordinatorEntity.__init__(
            self, store.coordinators[repository.data.category]
        )
        StoreEntity.__init__(self, store=store)
        self.repository = repository
        self._attr_unique_id = str(repository.data.id)
        self._repo_last_fetched = repository.data.last_fetched

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.store.repositories.is_downloaded(
            repository_id=str(self.repository.data.id)
        )

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about the Marketplace itself."""

        def _manufacturer() -> str:
            if authors := self.repository.data.authors:
                return ", ".join(author.replace("@", "") for author in authors)
            return self.repository.data.full_name.split("/")[0]

        return DeviceInfo(
            identifiers={(DOMAIN, str(self.repository.data.id))},
            name=self.repository.display_name,
            model=self.repository.data.category,
            manufacturer=_manufacturer(),
            configuration_url=f"homeassistant://marketplace/repository/{self.repository.data.id}",
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self._repo_last_fetched is not None
            and self.repository.data.last_fetched is not None
            and self._repo_last_fetched >= self.repository.data.last_fetched
        ):
            return

        self._repo_last_fetched = self.repository.data.last_fetched
        self.async_write_ha_state()

    @override
    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
