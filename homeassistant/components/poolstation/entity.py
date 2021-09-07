"""Base class for Poolstation entity."""
from __future__ import annotations

from pypoolstation import Pool

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PoolstationDataUpdateCoordinator
from .const import DOMAIN


class PoolEntity(CoordinatorEntity):
    """Representation of a pool entity."""

    coordinator: PoolstationDataUpdateCoordinator

    def __init__(
        self,
        pool: Pool,
        coordinator: PoolstationDataUpdateCoordinator,
        entity_suffix: str,
    ) -> None:
        """Init from config, hookup pool and coordinator."""
        super().__init__(coordinator)
        self._pool = pool

        pool_id = self._pool.id
        name = self._pool.alias

        self._attr_name = f"{name}{entity_suffix}"
        self._attr_unique_id = f"{pool_id}{entity_suffix}"
        self._attr_device_info = {"name": name, "identifiers": {(DOMAIN, pool_id)}}

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available  # for now, IDK if I can tell or not.
