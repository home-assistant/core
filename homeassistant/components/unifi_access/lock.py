"""Lock entities for the UniFi Access integration."""

from typing import Any

from uiaccessclient import ApiClient, SpaceApi

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UniFiAccessConfigEntry, UniFiAccessDoorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniFiAccessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure lock entities."""
    api_client = entry.runtime_data.api_client
    door_coordinator = entry.runtime_data.door_coordinator

    async_add_entities(
        UniFiAccessDoorLock(hass, api_client, door_coordinator, door_id)
        for door_id in door_coordinator.data
    )


class UniFiAccessDoorLock(CoordinatorEntity[UniFiAccessDoorCoordinator], LockEntity):
    """Represents a UniFi Access door lock."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: ApiClient,
        coordinator: UniFiAccessDoorCoordinator,
        door_id: str,
    ) -> None:
        """Initialize the door lock."""
        super().__init__(coordinator, context=door_id)

        self.hass = hass
        self.space_api = SpaceApi(api_client)

        self._attr_unique_id = door_id
        self._update_attributes()

    @property
    def translation_key(self) -> str:
        """Return the translation key to translate the entity's states."""
        return "door_lock"

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self) -> None:
        assert isinstance(self.unique_id, str)
        door = self.coordinator.data[self.unique_id]
        self._attr_is_locked = door.door_lock_relay_status == "lock"
        self._attr_is_open = door.door_position_status == "open"

    async def async_unlock(self, **kwargs: Any) -> None:
        """Lock the door."""
        assert isinstance(self.unique_id, str)
        await self.hass.async_add_executor_job(
            self.space_api.remote_door_unlocking, self.unique_id
        )

        self._attr_is_locked = False
        self.async_write_ha_state()
