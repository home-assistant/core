
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytedee_async import Lock as TedeeLock

from .const import DOMAIN


@dataclass
class TedeeEntityDescriptionMixin():
    """Describes Tedee entity."""
    unique_id_fn: Callable[[TedeeLock], str]


@dataclass
class TedeeEntityDescription(
        EntityDescription,
        TedeeEntityDescriptionMixin
    ):
    """Describes Tedee entity."""


class TedeeEntity(CoordinatorEntity):

    def __init__(self, lock, coordinator, entity_description):
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._lock = lock
        self._attr_has_entity_name = True
        self._attr_unique_id = self.entity_description.unique_id_fn(self._lock)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._lock.id)},
            name=self._lock.name,
            manufacturer="tedee",
            model=self._lock.type
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._lock = self.coordinator.data[self._lock.id]
        self.async_write_ha_state()