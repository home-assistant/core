"""Entity base classes for the VRChat integration."""

import re
from typing import TYPE_CHECKING, override

from propcache.api import cached_property

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .api_data_types import User
from .utils import process_vrchat_string
from .world import VRChatWorldData

if TYPE_CHECKING:
    from .coordinator import VRChatUserDataCoordinator


class VRChatUserDataEntity(Entity):
    """ABC for an entity that represents a VRChat user data point."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    should_add_for_current_user = True
    should_add_for_non_current_user = True

    subscribe_to_world_update = False

    VRCHAT_ENTITY_PLATFORM: str | None = None

    @override
    def __init_subclass__(cls, platform: str | None = None, **kwargs):
        """Register subclass."""
        if platform is not None:
            cls.VRCHAT_ENTITY_PLATFORM = platform
        elif (platform := cls.VRCHAT_ENTITY_PLATFORM) is not None:
            cls._register_vrchat_user_data_entity_subclass(platform)
        return super().__init_subclass__(**kwargs)

    def __init__(self, user: VRChatUserDataCoordinator) -> None:
        """Initialize the entity."""
        self.user = user

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to updates after the entity has joined Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.user.async_add_entity_update_listener(self._async_handle_user_update)
        )

    def _async_handle_user_update(
        self, force_refresh: bool, world_update: bool
    ) -> None:
        """Write state after data changes."""
        if not world_update or self.subscribe_to_world_update:
            self.async_schedule_update_ha_state(force_refresh=force_refresh)

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.user.account.available

    @property
    @override
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        return self.user.device_info

    @cached_property
    @override
    def unique_id(self):
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
        return user_data.get("presence", {}).get(key)

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
        return self.get_state_from_user_data(self.user.data)

    def vrchat_user_world_data_get[T](self, key: str, default: T | None = None):
        """Return a value from the user's world data."""
        if (world := self.user.world or self.user.destination_world) is not None and (
            data := world.data
        ) is not None:
            return data.get(key, default)
        return default

    @classmethod
    def should_add(cls, user: VRChatUserDataCoordinator) -> bool:
        """Determine whether this entity should be added."""
        return (
            (user.is_current_user and cls.should_add_for_current_user)
            or (user.is_not_current_user and cls.should_add_for_non_current_user)
        ) and cls.should_add_based_on_user_data(user.data)

    @classmethod
    def should_add_based_on_user_data(cls, user_data):
        """Determine whether this entity should be added from user data."""
        return cls.get_state_from_user_data(user_data) is not None

    @classmethod
    def _register_vrchat_user_data_entity_subclass(cls, platform: str) -> None:
        vrchat_user_data_entity_classes_map.setdefault(platform, []).append(cls)


vrchat_user_data_entity_classes_map: dict[str, list[type[VRChatUserDataEntity]]] = {}


class VRChatUserLocationEntityMixin:
    """Mixin for VRChat user location entities."""

    user: VRChatUserDataCoordinator
    subscribe_to_world_update = True

    @classmethod
    def should_add_based_on_user_data(cls, user_data):
        """Always add user location data."""
        return True

    async def async_update(self) -> None:
        """Wait for the world data update task if necessary."""
        world: VRChatWorldData | None = self.user.world or self.user.destination_world

        if world is None or world.data is not None:
            return
        if world.task is not None:
            await world.task
