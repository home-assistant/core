"""Setup sensors for the VRChat integration."""

import asyncio
from typing import cast, override

from vrchatapi.highlevel.presence import (
    VRCHAT_WORLD_ID_PREFIX,
    VRChatSpecialLocationString,
    is_user_in_game,
    process_vrchat_string,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import StateType

from .const import (
    VRCHAT_USER_STATE_OPTIONS,
    VRCHAT_USER_STATUS_ICON_MAP,
    VRCHAT_USER_STATUS_OPTIONS,
    VRChatUserState,
)
from .coordinator import VRChatConfigEntry
from .entity import VRChatUserDataEntity, VRChatUserLocationEntityMixin
from .utils import normalize_vrchat_enum_value


async def _async_cancel_discovery_tasks(tasks: tuple[asyncio.Task[None], ...]) -> None:
    """Cancel pending registration and wait for platform cleanup."""
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VRChatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator = config_entry.runtime_data
    coordinator.async_register_account_device()
    platform = async_get_current_platform()
    known_sensor_types: dict[str, set[type[VRChatUserDataSensorEntity]]] = {}
    pending: set[asyncio.Task[None]] = set()
    user_tasks: dict[str, set[asyncio.Task[None]]] = {}
    removing: set[str] = set()
    stopped = False

    async def async_add_user_entities(
        user_id: str,
        entities: list[VRChatUserDataSensorEntity],
    ) -> None:
        """Add a batch independently of other pending location metadata."""
        try:
            await platform.async_add_entities(entities, update_before_add=True)
        except asyncio.CancelledError:
            if user_id not in removing:
                raise

    async def async_prepare_user_removal(user_id: str) -> None:
        """Finish pending registration before the SDK commits removal."""
        removing.add(user_id)
        await _async_cancel_discovery_tasks(tuple(user_tasks.pop(user_id, ())))
        known_sensor_types.pop(user_id, None)

    @callback
    def async_add_new_entities() -> None:
        if stopped:
            return
        removing.intersection_update(coordinator.data)
        for user_id in known_sensor_types.keys() - coordinator.data.keys():
            known_sensor_types.pop(user_id)
        for user_id, user in coordinator.data.items():
            if user_id in removing:
                continue
            sensor_types = known_sensor_types.setdefault(user_id, set())
            new_entities: list[VRChatUserDataSensorEntity] = []
            for sensor_class in SENSOR_CLASSES:
                if sensor_class not in sensor_types and sensor_class.should_add(
                    user, user_id == config_entry.unique_id
                ):
                    sensor_types.add(sensor_class)
                    new_entities.append(sensor_class(coordinator, user_id))
            if new_entities:
                task = config_entry.async_create_task(
                    hass,
                    async_add_user_entities(user_id, new_entities),
                    f"Add VRChat entities for {user_id}",
                    eager_start=False,
                )
                pending.add(task)
                task.add_done_callback(pending.discard)
                tasks = user_tasks.setdefault(user_id, set())
                tasks.add(task)
                task.add_done_callback(tasks.discard)

    async def async_stop_discovery() -> None:
        """Stop scheduling work before cancelling pending registrations."""
        nonlocal stopped
        stopped = True
        await _async_cancel_discovery_tasks(tuple(pending))
        pending.clear()

    config_entry.async_on_unload(
        coordinator.async_register_user_removal_callback(async_prepare_user_removal)
    )
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))
    config_entry.async_on_unload(async_stop_discovery)
    async_add_new_entities()
    while pending:
        tasks_to_wait = tuple(pending)
        await asyncio.gather(*tasks_to_wait)
        pending.difference_update(tasks_to_wait)


class VRChatUserDataSensorEntity(VRChatUserDataEntity, SensorEntity):
    """Base entity for all VRChat sensors."""

    @property
    @override
    def native_value(self) -> StateType:
        """The state."""
        return self.vrchat_user_data_state


class VRChatUserStatusSensor(VRChatUserDataSensorEntity):
    """VRChat user status sensor entity."""

    entity_description = SensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=VRCHAT_USER_STATUS_OPTIONS,
    )

    @classmethod
    @override
    def get_state_from_user_data(cls, user_data, key=None):
        """Return a normalized VRChat user status."""
        status = normalize_vrchat_enum_value(
            super().get_state_from_user_data(user_data, key)
        )
        return status if status in VRCHAT_USER_STATUS_OPTIONS else None


class VRChatUserStatusDescriptionSensor(VRChatUserDataSensorEntity):
    """VRChat user status description sensor entity."""

    entity_description = SensorEntityDescription(
        key="statusDescription", translation_key="status_description"
    )

    @property
    @override
    def icon(self) -> str | None:
        """Show icon based on user status."""
        return VRCHAT_USER_STATUS_ICON_MAP.get(
            VRChatUserStatusSensor.get_state_from_user_data(self.user_data)
        )


class VRChatUserStateSensor(VRChatUserDataSensorEntity):
    """VRChat user state sensor entity."""

    entity_description = SensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=VRCHAT_USER_STATE_OPTIONS,
    )

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the user icon or avatar image."""
        user_data_get = self.user_data.get
        return process_vrchat_string(
            cast(
                str | None,
                user_data_get("iconUrl")
                or user_data_get("userIcon")
                or user_data_get("imageUrl")
                or user_data_get("currentAvatarThumbnailImageUrl")
                or user_data_get("currentAvatarImageUrl"),
            )
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


class VRChatUserLocationSensor(
    VRChatUserLocationEntityMixin, VRChatUserDataSensorEntity
):
    """VRChat user location sensor entity."""

    _attr_native_value = None

    entity_description = SensorEntityDescription(
        key="location", translation_key="location", device_class=SensorDeviceClass.ENUM
    )

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the world thumbnail URL."""
        if self.get_state_from_user_data(self.user_data, "location") in (
            VRChatSpecialLocationString.PRIVATE,
            VRChatSpecialLocationString.OFFLINE,
        ):
            return None
        return self.vrchat_user_world_data_get("thumbnailImageUrl")

    @property
    @override
    def options(self):
        """Return special locations and all cached world names."""
        client = self.coordinator.client
        assert client is not None
        special_options = [
            *(location.value for location in VRChatSpecialLocationString),
            VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE.value,
        ]
        return [
            *special_options,
            *(
                name
                for name in client.worlds.sorted_names
                if name not in special_options
            ),
        ]

    @property
    @override
    def vrchat_user_data_state(self):
        """World name."""
        if (
            VRChatUserStateSensor.get_state_from_user_data(self.user_data)
            == VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE
        ):
            self._attr_native_value = VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE.value
        elif (
            location := self.get_state_from_user_data(self.user_data, "location")
        ) is not None and location.startswith(VRChatSpecialLocationString.TRAVELING):
            self._attr_native_value = VRChatSpecialLocationString.TRAVELING.value
        elif location in (
            VRChatSpecialLocationString.PRIVATE,
            VRChatSpecialLocationString.OFFLINE,
        ):
            self._attr_native_value = location
        else:
            name = self.vrchat_user_world_data_get("name")
            if name == "":
                self._attr_native_value = self.get_state_from_user_data(
                    self.user_data, "worldId"
                )
            else:
                if name is None:
                    name = self.get_state_from_user_data(self.user_data, "worldId")
                # Preserve the last resolved name while metadata retries to avoid showing a world ID.
                if name is not None and not name.startswith(VRCHAT_WORLD_ID_PREFIX):
                    self._attr_native_value = name
        return self._attr_native_value


SENSOR_CLASSES: tuple[type[VRChatUserDataSensorEntity], ...] = (
    VRChatUserStatusSensor,
    VRChatUserStatusDescriptionSensor,
    VRChatUserStateSensor,
    VRChatUserLocationSensor,
)
