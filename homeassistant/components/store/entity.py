"""HACS Base entities."""

from typing import TYPE_CHECKING, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import BaseCoordinatorEntity

from .const import DOMAIN
from .coordinator import HacsUpdateCoordinator

if TYPE_CHECKING:
    from .base import HacsBase
    from .repositories.base import HacsRepository


class HacsBaseEntity(Entity):
    """Base HACS entity."""

    repository: HacsRepository
    _attr_should_poll = False

    def __init__(self, hacs: HacsBase) -> None:
        """Initialize."""
        self.hacs = hacs


class HacsRepositoryEntity(
    BaseCoordinatorEntity[HacsUpdateCoordinator], HacsBaseEntity
):
    """Base repository entity."""

    def __init__(
        self,
        hacs: HacsBase,
        repository: HacsRepository,
    ) -> None:
        """Initialize."""
        BaseCoordinatorEntity.__init__(
            self, hacs.coordinators[repository.data.category]
        )
        HacsBaseEntity.__init__(self, hacs=hacs)
        self.repository = repository
        self._attr_unique_id = str(repository.data.id)
        self._repo_last_fetched = repository.data.last_fetched

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.hacs.repositories.is_downloaded(
            repository_id=str(self.repository.data.id)
        )

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about HACS."""

        def _manufacturer() -> str:
            if authors := self.repository.data.authors:
                return ", ".join(author.replace("@", "") for author in authors)
            return self.repository.data.full_name.split("/")[0]

        return DeviceInfo(
            identifiers={(DOMAIN, str(self.repository.data.id))},
            name=self.repository.display_name,
            model=self.repository.data.category,
            manufacturer=_manufacturer(),
            configuration_url=f"homeassistant://store/repository/{self.repository.data.id}",
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
