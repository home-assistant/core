"""Entity base classes for the VRChat integration."""

from collections.abc import Mapping
import re
from typing import override

from propcache.api import cached_property
from vrchatapi.highlevel import VRChatUser, VRChatWorldData
from vrchatapi.highlevel.presence import process_vrchat_string
from vrchatapi.highlevel.types import HighLevelUserData, User

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VRCHAT_USER_PAGE_BASE_URL
from .coordinator import VRChatAccountDataCoordinator


class VRChatUserDataEntity(CoordinatorEntity[VRChatAccountDataCoordinator]):
    """ABC for an entity that represents a VRChat user data point."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    should_add_for_current_user = True
    should_add_for_non_current_user = True

    subscribe_to_world_update = False

    def __init__(self, coordinator: VRChatAccountDataCoordinator, user_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, context=user_id)
        self.user_id = user_id

    @property
    def user(self) -> VRChatUser | None:
        """Return the current library user, if still present."""
        return self.coordinator.data.get(self.user_id)

    @property
    def user_data(self) -> HighLevelUserData:
        """Return the current user snapshot."""
        return self.user.data if self.user is not None else {}

    @property
    def world(self) -> VRChatWorldData | None:
        """Return the current world."""
        return self.user.world if self.user is not None else None

    @property
    def destination_world(self) -> VRChatWorldData | None:
        """Return the destination world."""
        return self.user.destination_world if self.user is not None else None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Write state after data changes."""
        if (
            self.user_id in self.coordinator.data
            and self.coordinator.updated_user_id in (None, self.user_id)
            and (not self.coordinator.world_update or self.subscribe_to_world_update)
        ):
            self.async_schedule_update_ha_state(
                force_refresh=self.coordinator.force_refresh
            )

    @override
    async def async_update(self) -> None:
        """Use the user snapshot maintained by the library."""

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.available and self.user_id in self.coordinator.data

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        entry = self.coordinator.config_entry
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}:{self.user_id}")},
            name=self.user_data.get("displayName"),
            configuration_url=VRCHAT_USER_PAGE_BASE_URL + self.user_id,
        )
        if self.user_id != entry.unique_id:
            device_info["via_device_id"] = dr.async_get_device_id_by_identifier(
                self.coordinator.hass,
                (DOMAIN, f"{entry.unique_id}:{entry.unique_id}"),
                config_entry_id=entry.entry_id,
            )
        return device_info

    @cached_property
    @override
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{self.entity_description.key}.{next(iter(self.device_info['identifiers']))[1]}"

    @cached_property
    @override
    def translation_key(self):
        """Return the translation key."""
        return re.sub(r"(?<!^)(?=[A-Z])", "_", self.entity_description.key).lower()

    @classmethod
    def get_raw_state_from_user_data(cls, user_data: User, key: str | None = None):
        """Return raw state from user data."""
        if key is None:
            key = cls.entity_description.key
        if key in user_data:
            return user_data.get(key)
        presence = user_data.get("presence")
        return presence.get(key) if isinstance(presence, Mapping) else None

    @classmethod
    def get_state_from_user_data(cls, user_data: User, key: str | None = None):
        """Return state from user data."""
        state = cls.get_raw_state_from_user_data(user_data, key)
        if isinstance(state, str):
            return process_vrchat_string(state)
        return state

    @property
    def vrchat_user_data_state(self):
        """Return the state."""
        return self.get_state_from_user_data(self.user_data)

    def vrchat_user_world_data_get[T](self, key: str, default: T | None = None):
        """Return a value from the user's world data."""
        if (world := self.world or self.destination_world) is not None and (
            data := world.data
        ) is not None:
            return data.get(key, default)
        return default

    @classmethod
    def should_add(cls, user: VRChatUser, is_current_user: bool) -> bool:
        """Determine whether this entity should be added."""
        return (
            (is_current_user and cls.should_add_for_current_user)
            or (not is_current_user and cls.should_add_for_non_current_user)
        ) and cls.should_add_based_on_user_data(user.data)

    @classmethod
    def should_add_based_on_user_data(cls, user_data):
        """Determine whether this entity should be added from user data."""
        return cls.get_state_from_user_data(user_data) is not None


class VRChatUserLocationEntityMixin:
    """Mixin for VRChat user location entities."""

    world: VRChatWorldData | None
    destination_world: VRChatWorldData | None
    subscribe_to_world_update = True

    @classmethod
    def should_add_based_on_user_data(cls, user_data):
        """Always add user location data."""
        return True

    async def async_update(self) -> None:
        """Wait for the world data update task if necessary."""
        world: VRChatWorldData | None = self.world or self.destination_world

        if world is None or world.data is not None:
            return
        if world.task is not None:
            await world.get_data()
