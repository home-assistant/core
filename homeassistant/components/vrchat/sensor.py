"""Setup sensors for the VRChat integration."""

from collections.abc import Mapping
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    VRCHAT_USER_STATE_OPTIONS,
    VRCHAT_USER_STATUS_ICON_MAP,
    VRCHAT_USER_STATUS_INDICATOR_MAP_IN_GAME,
    VRCHAT_USER_STATUS_INDICATOR_MAP_NOT_IN_GAME,
    VRCHAT_USER_STATUS_OPTIONS,
    VRChatUserState,
)
from .coordinator import VRChatConfigEntry
from .entity import VRChatUserDataEntity, VRChatUserLocationEntityMixin
from .utils import (
    VRCHAT_WORLD_ID_PREFIX,
    VRChatSpecialLocationString,
    is_user_in_game,
    normalize_vrchat_enum_value,
    process_vrchat_string,
)
from .world import VRChatWorldData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VRChatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    config_entry.runtime_data.setup_entities(Platform.SENSOR, async_add_entities)


class VRChatUserDataSensorEntity(
    VRChatUserDataEntity, SensorEntity, platform=Platform.SENSOR
):
    """Base entity for all VRChat sensors."""

    @property
    @override
    def native_value(self):
        """The state."""
        return self.vrchat_user_data_state


class VRChatUserStatusSensor(VRChatUserDataSensorEntity):
    """VRChat user status sensor entity."""

    entity_description = SensorEntityDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=VRCHAT_USER_STATUS_OPTIONS,
    )

    @classmethod
    @override
    def get_state_from_user_data(cls, user_data, key=None):
        """Return a normalized VRChat user status."""
        return normalize_vrchat_enum_value(
            super().get_state_from_user_data(user_data, key)
        )

    @property
    @override
    def entity_picture(self):
        """Return the user status indicator."""
        status = self.native_value
        if status is None:
            return None
        # VRChat renders offline and in-game states with the same solid-circle indicator.
        if status == VRChatUserState.OFFLINE or is_user_in_game(self.user.data):
            return VRCHAT_USER_STATUS_INDICATOR_MAP_IN_GAME.get(status)
        return VRCHAT_USER_STATUS_INDICATOR_MAP_NOT_IN_GAME.get(status)


class VRChatUserStatusDescriptionSensor(VRChatUserDataSensorEntity):
    """VRChat user status description sensor entity."""

    entity_description = SensorEntityDescription(key="statusDescription")

    @property
    @override
    def icon(self) -> str | None:
        """Show icon based on user status."""
        return VRCHAT_USER_STATUS_ICON_MAP.get(
            VRChatUserStatusSensor.get_state_from_user_data(self.user.data)
        )


class VRChatUserStateSensor(VRChatUserDataSensorEntity):
    """VRChat user state sensor entity."""

    entity_description = SensorEntityDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=VRCHAT_USER_STATE_OPTIONS,
    )

    @property
    @override
    def entity_picture(self):
        """Return the user icon or avatar image."""
        user_data_get = self.user.data.get
        return process_vrchat_string(
            user_data_get("userIcon")
            or user_data_get("imageUrl")
            or user_data_get("currentAvatarThumbnailImageUrl")
        )

    @classmethod
    @override
    def get_state_from_user_data(cls, user_data, key=None):
        """Summarize user state."""
        is_in_game = is_user_in_game(user_data)
        if is_in_game is None:
            return None
        status = VRChatUserStatusSensor.get_state_from_user_data(user_data)
        if is_in_game:
            return status
        if status == VRChatUserState.OFFLINE:
            return VRChatUserState.OFFLINE.value
        return VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE.value

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """User data."""
        return self.user.data


class VRChatUserLocationSensor(
    VRChatUserLocationEntityMixin, VRChatUserDataSensorEntity
):
    """VRChat user location sensor entity."""

    _attr_native_value = None

    entity_description = SensorEntityDescription(
        key="location", device_class=SensorDeviceClass.ENUM
    )

    @property
    @override
    def entity_picture(self):
        """Return the world thumbnail URL."""
        return self.vrchat_user_world_data_get("thumbnailImageUrl")

    @property
    @override
    def options(self):
        """Dynamically return options based on known locations."""
        special_options = [
            *(location.value for location in VRChatSpecialLocationString),
            VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE.value,
        ]
        return [
            *special_options,
            *sorted(
                {
                    name
                    for world in VRChatWorldData.registry.values()
                    if (data := world.data) is not None
                    and (name := data.get("name")) is not None
                    and name not in special_options
                }
            ),
        ]

    @property
    @override
    def vrchat_user_data_state(self):
        """World name."""
        if (
            VRChatUserStateSensor.get_state_from_user_data(self.user.data)
            == VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE
        ):
            self._attr_native_value = VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE.value
        elif (
            location := self.get_state_from_user_data(self.user.data, "location")
        ) is not None and location.startswith(VRChatSpecialLocationString.TRAVELING):
            self._attr_native_value = VRChatSpecialLocationString.TRAVELING.value
        else:
            name = self.vrchat_user_world_data_get("name")
            if name is None:
                name = self.get_state_from_user_data(self.user.data, "worldId")
            # Preserve the last resolved name while metadata retries to avoid showing a world ID.
            if name is not None and not name.startswith(VRCHAT_WORLD_ID_PREFIX):
                self._attr_native_value = name
        return self._attr_native_value

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """World data."""
        user_data_get = self.user.data.get
        if (world := self.user.world) is not None and (data := world.data) is not None:
            return {"instanceId": user_data_get("instanceId"), **data}
        return {
            "id": user_data_get("worldId"),
            "instanceId": user_data_get("instanceId"),
            "travelingToLocation": user_data_get("travelingToLocation"),
        }
