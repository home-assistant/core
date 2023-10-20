"""Bases for Tedee entities."""
from collections.abc import Callable
from dataclasses import dataclass

from pytedee_async.lock import TedeeLock

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


@dataclass
class TedeeEntityDescriptionMixin:
    """Describes Tedee entity."""

    unique_id_fn: Callable[[TedeeLock], str]


@dataclass
class TedeeEntityDescription(EntityDescription, TedeeEntityDescriptionMixin):
    """Describes Tedee entity."""


class TedeeEntity(CoordinatorEntity):
    """Base class for Tedee entities."""

    entity_description: TedeeEntityDescription

    def __init__(self, lock, coordinator, entity_description) -> None:
        """Initialize Tedee entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._lock = lock
        self._attr_has_entity_name = True
        self._attr_unique_id = self.entity_description.unique_id_fn(self._lock)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._lock.lock_id)},
            name=self._lock.lock_name,
            manufacturer="tedee",
            model=self._lock.lock_type,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._lock = self.coordinator.data[self._lock.lock_id]
        self.async_write_ha_state()
