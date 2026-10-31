"""Setup sensors for the VRChat integration."""

import asyncio
from typing import cast, override

from vrchatapi.highlevel import VRChatUser
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
from homeassistant.helpers import entity_registry as er
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
    entity_registry = er.async_get(hass)
    known_users: dict[str, VRChatUser] = {}
    known_entities: dict[
        str, dict[type[VRChatUserDataSensorEntity], VRChatUserDataSensorEntity]
    ] = {}
    pending: set[asyncio.Task[None]] = set()
    user_tasks: dict[str, set[asyncio.Task[None]]] = {}
    retiring: set[str] = set()
    stopped = False

    async def async_add_user_entities(
        user_id: str,
        user: VRChatUser,
        entities: list[VRChatUserDataSensorEntity],
    ) -> None:
        """Add independent sensor batches without waiting for location metadata."""
        try:
            if coordinator.data.get(user_id) is user and user_id not in retiring:
                await platform.async_add_entities(entities, update_before_add=True)
        except asyncio.CancelledError:
            if user_id not in retiring:
                raise

    async def async_remove_user_entities(
        user_id: str,
        tasks: tuple[asyncio.Task[None], ...],
        removals: list[asyncio.Task[None]],
    ) -> None:
        """Finish a deleted generation before the same user can be discovered again."""
        try:
            await _async_cancel_discovery_tasks(tasks)
            await asyncio.gather(*removals)
            for entity in known_entities.pop(user_id).values():
                if entity_registry.async_get(entity.entity_id) is not None:
                    entity_registry.async_remove(entity.entity_id)
                if platform.entities.get(entity.entity_id) is entity:
                    await entity.async_remove(force_remove=True)
            known_users.pop(user_id)
        finally:
            retiring.discard(user_id)
        async_add_new_entities()

    @callback
    def async_add_new_entities() -> None:
        if stopped:
            return
        for user_id, user in list(known_users.items()):
            if user_id in retiring or coordinator.data.get(user_id) is user:
                continue
            retiring.add(user_id)
            add_tasks = tuple(user_tasks.pop(user_id, ()))
            for task in add_tasks:
                task.cancel()
            # Retire live entities before the coordinator invokes remaining listeners.
            removals = [
                config_entry.async_create_task(
                    hass,
                    entity.async_remove(force_remove=True),
                    f"Remove VRChat entity {entity.entity_id}",
                    eager_start=True,
                )
                for entity in known_entities[user_id].values()
                if platform.entities.get(entity.entity_id) is entity
            ]
            task = config_entry.async_create_task(
                hass,
                async_remove_user_entities(user_id, add_tasks, removals),
                f"Remove VRChat entities for {user_id}",
                eager_start=False,
            )
            pending.add(task)
            task.add_done_callback(pending.discard)

        for user_id, user in coordinator.data.items():
            if user_id in retiring:
                continue
            known_users[user_id] = user
            entities = known_entities.setdefault(user_id, {})
            new_entities: list[VRChatUserDataSensorEntity] = []
            for sensor_class in SENSOR_CLASSES:
                if sensor_class not in entities and sensor_class.should_add(
                    user, user_id == config_entry.unique_id
                ):
                    entity = sensor_class(coordinator, user_id)
                    entities[sensor_class] = entity
                    new_entities.append(entity)
            if new_entities:
                task = config_entry.async_create_task(
                    hass,
                    async_add_user_entities(user_id, user, new_entities),
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
