"""Data update coordinator for the VRChat integration."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import cache, cached_property
import json
import logging
import math
import re
from typing import Any, Final, cast, override

import vrchatapi
import vrchatapi.exceptions
from vrchatapi.websocket import VRChatWebSocket, VRChatWebSocketError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import VRChatAPI
from .api_data_types import User, WebsocketUserEvent, World
from .const import (
    DOMAIN,
    RETRY_DELAY_SECOND,
    VRCHAT_USER_PAGE_BASE_URL,
    WEBSOCKET_INACTIVE_TIMEOUT_SECOND,
    VRChatUserState,
    VRChatWebsocketEventType,
)
from .store import InitialCurrentUserData, get_vrchat_auth_cookie_store
from .utils import (
    VRCHAT_SPECIAL_LOCATION_STRINGS,
    AsyncCleanups,
    parse_vrchat_location_string,
    process_vrchat_string,
)
from .world import VRChatWorldData

VRCHAT_WEBSOCKET_EVENT_TYPES_WITH_STRING_CONTENT = {
    "see-notification",
    "hide-notification",
}

EXCEPTION_MESSAGE_VRCHAT_WEBSOCKET_EVENT: Final = (
    "Error handling VRChat websocket message."
)

_LOGGER = logging.getLogger(__name__)

type VRChatConfigEntry = ConfigEntry[VRChatAccountDataCoordinator]


class VRChatAccountDataCoordinator(AsyncCleanups):
    """Data update coordinator for VRChat account."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VRChatConfigEntry,
    ):
        """Initialization."""

        self.hass = hass
        self.device_registry = dr.async_get(hass)
        self.config_entry = entry
        assert entry.unique_id is not None
        self.cookie_store = get_vrchat_auth_cookie_store(self.hass, entry.unique_id)

        self.users: dict[str, VRChatUserDataCoordinator] = {}

        self.ws: VRChatWebSocket | None = None
        self.ws_handler_task: asyncio.Task | None = None

        self._available = False

        self.auto_restart = True

        self.add_entities_callback_map: dict[str, AddConfigEntryEntitiesCallback] = {}

        self.starting_task = self.create_task(self.__async_init__())
        self.add_to_cleanups(self.starting_task.cancel)

    async def __async_init__(self):
        """Async part of initialization."""

        try:
            self.api = VRChatAPI(
                self.config_entry.data,
                await self.cookie_store.async_load(),
            )
            self.add_to_cleanups(self.api.close)

            if self.config_entry.unique_id in InitialCurrentUserData:
                self.current_user_data = InitialCurrentUserData.pop(
                    self.config_entry.unique_id
                )
            else:
                await self.authenticate()

            await self.ws_connect()

            await self.fetch_users()

        except ConfigEntryAuthFailed:
            raise
        except ConfigEntryNotReady:
            raise
        except ConfigEntryError:
            raise
        except Exception as e:
            _LOGGER.exception("Unknown setup error")
            raise VRChatAccountSetupFailed(self.config_entry) from e

    def create_task[T](
        self,
        task: Coroutine[Any, Any, T],
        name: str | None = None,
        eager_start: bool = True,
    ):
        """Create task."""
        return self.config_entry.async_create_task(self.hass, task, name, eager_start)

    async def use_api[T](self, callback: Callable[[VRChatAPI], Coroutine[Any, Any, T]]):
        """Use the API in a safe way.

        Get a fresh copy of the API in the callback.
        The callback will be called a second time after reauthentication if an authentication error happened in the first try.
        """
        try:
            return await callback(self.api.copy())
        except vrchatapi.exceptions.UnauthorizedException:
            await self.restart()
            return await callback(self.api)

    @cached_property
    def current_user(self):
        """Current user data coordinator."""
        return self.users[self.config_entry.unique_id]

    @cached_property
    def username(self):
        """Username of current user."""
        return self.current_user_data["username"]

    @property
    def available(self):
        """Available."""
        return self._available

    @available.setter
    def available(self, new_value: bool):
        if self._available == new_value:
            return
        self._available = new_value
        if new_value:
            _LOGGER.info("Account %s is available.", self.username)
        else:
            _LOGGER.warning("Account %s is unavailable", self.username)
        for user in self.users.values():
            user.async_update_entities(force_refresh=new_value)

    def setup_entities(
        self, platform: str, add_entities: AddConfigEntryEntitiesCallback
    ):
        """Setup entities."""
        self.add_entities_callback_map[platform] = add_entities
        for user in self.users.values():
            user.setup_entities(platform)

    async def authenticate(self):
        """Authenticate and fetch current user."""
        try:
            current_user_data = await self.api.get_current_user()
        except vrchatapi.exceptions.UnauthorizedException as e:
            raise VRChatAccountAuthFailed(self.config_entry) from e
        except Exception as e:
            raise VRChatAccountSetupFailed(self.config_entry) from e
        if current_user_data["id"] != self.config_entry.unique_id:
            raise ConfigEntryError(
                f"User ID does not match the ID of this config entry. Please reconfigure and make sure the account is correct or add a new entry instead.\nExpected ID: {self.config_entry.unique_id}\nGot ID: {current_user_data['id']}",
                translation_domain=DOMAIN,
                translation_key="unique_id_mismatch",
                translation_placeholders={
                    "config_entry_title": self.config_entry.title,
                    "expected_id": self.config_entry.unique_id,
                    "got_id": current_user_data["id"],
                },
            )
        self.current_user_data = current_user_data
        await self.cookie_store.async_save(self.api.cookie)

    async def fetch_users(self):
        """Fetch full list of users."""
        friend_ids = self.current_user_data["friends"]
        async with asyncio.TaskGroup() as tg:
            online_friends_task = tg.create_task(self._get_friends(False))
            offline_friends_task = tg.create_task(self._get_friends(True))
            for i in self.users:
                if not (i == self.current_user_data["id"] or i in friend_ids):
                    tg.create_task(self.users[i].close())
        self.set_user(self.current_user_data)
        offline_friends = offline_friends_task.result()
        online_friends = online_friends_task.result()
        for f in offline_friends:
            self.set_user(f)
        for f in online_friends:
            self.set_user(f)
        fetched_friend_ids = [f["id"] for f in [*offline_friends, *online_friends]]
        async with asyncio.TaskGroup() as tg:
            for i in friend_ids:
                if i not in fetched_friend_ids:
                    tg.create_task(self.api.get_user(i)).add_done_callback(
                        lambda task: self.set_user(task.result())
                    )

    async def _get_friends(self, offline: bool) -> list[User]:
        friend_ids: list[str] = (
            self.current_user_data["offlineFriends"]
            if offline
            else self.current_user_data["onlineFriends"]
        )
        if len(friend_ids) <= 0:
            return []
        page_size = 100
        page_count = math.ceil(len(friend_ids) / page_size)
        friends: list[User] = []
        async with asyncio.TaskGroup() as tg:
            for i in range(page_count):
                tg.create_task(
                    self.api.get_friends(
                        offset=i * page_size, n=page_size, offline=offline
                    )
                ).add_done_callback(lambda task: friends.extend(task.result()))
        return friends

    def set_user(self, data: User, overwrite=True):
        """Set a user data dict to users dict."""
        user_id = data["id"]
        if user_id in self.users:
            if overwrite:
                user = self.users[user_id]
                user.data = data
        else:
            user = VRChatUserDataCoordinator(self, data)
            self.users[user_id] = user
            user.setup_entities()
        return user

    async def ensure_user(self, user_id: str):
        """Fetch user if not exist. If exist, do nothing."""
        if user_id in self.users:
            return self.users[user_id]
        return self.set_user(await self.api.get_user(user_id), False)

    async def ws_connect(self):
        """Connect to websocket API."""
        old_ws = self.ws
        old_ws_handler_task = self.ws_handler_task
        self.ws = await self.api.ws_connect()
        self.ws.on_error(self._ws_error_handler)
        self.available = True
        self.ws_handler_task = asyncio.create_task(self.ws_handler())
        self.ws_handler_task.add_done_callback(self.ws_handler_done(self.ws))
        self.add_to_cleanups(self.ws.close)
        self.add_to_cleanups(self.ws_handler_task.cancel)
        if old_ws is not None:
            self.create_task(old_ws.close())
            self.remove_from_cleanups(old_ws.close)
        if old_ws_handler_task is not None:
            old_ws_handler_task.cancel()

    async def ws_handler(self):
        """Handle websocket messages."""
        try:
            async with asyncio.timeout(WEBSOCKET_INACTIVE_TIMEOUT_SECOND) as timeout:
                async for event in self.ws:
                    timeout.reschedule(
                        asyncio.get_running_loop().time()
                        + WEBSOCKET_INACTIVE_TIMEOUT_SECOND
                    )
                    try:
                        self._handle_ws_message(json.loads(event.raw))
                    except Exception:
                        _LOGGER.exception(EXCEPTION_MESSAGE_VRCHAT_WEBSOCKET_EVENT)
        except TimeoutError:
            self.ws_handler_task = self.create_task(self.ws_handler())
            raise

    def _handle_ws_message(self, data: dict[str, Any]) -> None:
        """Handle a single websocket message."""
        data["account_id"] = self.config_entry.unique_id
        data["config_entry_id"] = self.config_entry.entry_id
        try:
            if "type" in data:
                event_type = data["type"]
                if (
                    "content" in data
                    and event_type
                    not in VRCHAT_WEBSOCKET_EVENT_TYPES_WITH_STRING_CONTENT
                ):
                    try:
                        content: dict[str, Any] = json.loads(data["content"])
                        data["content"] = content
                        if "userId" in content:
                            user_id: str = content["userId"]
                            if user_id in self.users:
                                user = self.users[user_id]
                                data["old_user"] = user.data
                                if (device_entry := user.device_entry) is not None:
                                    data["device_id"] = device_entry.id
                                user.handle_event(cast(WebsocketUserEvent, data))
                            elif event_type != VRChatWebsocketEventType.FRIEND_DELETE:
                                if "user" in content:
                                    self.set_user(content["user"])
                                else:
                                    self.create_task(self.ensure_user(user_id))
                        if isinstance((world := content.get("world")), dict) and (
                            (world_id := process_vrchat_string(world.get("id")))
                            is not None
                        ):
                            VRChatWorldData.get(world_id, cast(World, world))
                        if (
                            (
                                world_id := parse_vrchat_location_string(
                                    content.get("travelingToLocation")
                                )[0]
                            )
                            is not None
                            and world_id not in VRCHAT_SPECIAL_LOCATION_STRINGS
                        ):
                            self.create_task(VRChatWorldData.get(world_id).get_data())
                            content["travelingToWorldId"] = world_id
                    except Exception:
                        _LOGGER.exception(EXCEPTION_MESSAGE_VRCHAT_WEBSOCKET_EVENT)
            else:
                data["type"] = "error" if "err" in data else "unknown"
                _LOGGER.error(data)
        finally:
            pass

    async def _ws_error_handler(self, exc: Exception) -> None:
        """Handle websocket errors."""
        if isinstance(exc, VRChatWebSocketError) and exc.raw is not None:
            try:
                data: dict[str, Any] = json.loads(exc.raw)
            except ValueError:
                return
            try:
                self._handle_ws_message(data)
            except Exception:
                _LOGGER.exception(EXCEPTION_MESSAGE_VRCHAT_WEBSOCKET_EVENT)
        else:
            _LOGGER.exception(EXCEPTION_MESSAGE_VRCHAT_WEBSOCKET_EVENT, exc_info=exc)

    def ws_handler_done(self, ws):
        """On websocket message handler done."""

        def callback(task: asyncio.Task):
            self.remove_from_cleanups(task.cancel)
            not_timeout = True
            try:
                task.result()
            except TimeoutError:
                not_timeout = False
            except asyncio.CancelledError:
                pass
            finally:
                if not_timeout and self.ws is ws:
                    self.available = False
                if self.auto_restart:
                    self.restart()

        return callback

    def restart(self, delay=0):
        """Reauthenticate and start connection."""
        _LOGGER.warning(
            "Restart scheduled for account %s in %s seconds.",
            self.username,
            delay,
        )
        self.starting_task.cancel()
        self.starting_task = self.create_task(self._restart(delay))
        return self.starting_task

    async def _restart(self, delay):
        old_api = self.api
        self.api = old_api.copy()
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            async with asyncio.timeout(RETRY_DELAY_SECOND):
                await self.authenticate()
                await self.ws_connect()
                await self.fetch_users()
        except ConfigEntryAuthFailed:
            self.auto_restart = False
            self.available = False
            _LOGGER.error(
                "VRChat authentication expired; reload the entry to sign in again."
            )
        except ConfigEntryError:
            raise
        except TimeoutError:
            if self.auto_restart:
                self.restart()
            raise
        except Exception:
            if self.auto_restart:
                self.restart(RETRY_DELAY_SECOND)
            raise
        finally:
            self.remove_from_cleanups(old_api.close)
            await old_api.close()

    @override
    def close(self):
        """Close."""
        self.auto_restart = False
        self.starting_task.cancel()
        return super().close()


class VRChatAccountSetupFailed(ConfigEntryNotReady):
    """VRChat account setup failed error."""

    def __init__(self, config_entry: VRChatConfigEntry):
        """Fill in info."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"config_entry_title": config_entry.title},
        )


class VRChatAccountAuthFailed(ConfigEntryAuthFailed):
    """VRChat account auth failed error."""

    def __init__(
        self,
        config_entry: VRChatConfigEntry,
        translation_key: str = "auth_failed",
        translation_placeholders: dict[str, str] | None = None,
    ):
        """Fill in info."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={
                "config_entry_title": config_entry.title,
                **(translation_placeholders or {}),
            },
        )


class VRChatUserDataCoordinator(AsyncCleanups):
    """Data update coordinator for VRChat user."""

    def __init__(self, account: VRChatAccountDataCoordinator, data: User):
        """Initialization."""

        self.added_entity_map: dict[
            type[VRChatUserDataEntity], VRChatUserDataEntity
        ] = {}
        self._entity_update_listeners: list[Callable[[bool, bool], None]] = []

        self.world: VRChatWorldData | None = None
        self._data: User

        self.account = account
        self.data = data

        account.add_to_cleanups(self.close)

    @property
    def data(self):
        """VRChat user data."""
        return self._data

    @data.setter
    def data(self, new_data: User):
        try:
            new_data["friend_of"] = self.account.current_user_data["id"]
            presence = new_data.get("presence", {})
            world_id = process_vrchat_string(presence.get("world"))
            instance_id = process_vrchat_string(presence.get("instance"))
            if (location := process_vrchat_string(new_data.get("location"))) is None:
                location = (
                    process_vrchat_string(presence.get("location"))
                    or world_id
                    or instance_id
                    or VRChatUserState.OFFLINE
                )
                new_data["location"] = location
            if "worldId" not in new_data or "instanceId" not in new_data:
                parsed_world_id, parsed_instance_id = parse_vrchat_location_string(
                    location
                )
                new_data.setdefault("worldId", parsed_world_id or world_id)
                new_data.setdefault("instanceId", parsed_instance_id or instance_id)
            world_id = new_data["worldId"]
            if (not hasattr(self, "_data")) or self._data.get("worldId") != world_id:
                if (world := self.world) is not None:
                    world.unsubscribe(
                        self.async_schedule_update_ha_state_of_world_entities
                    )
                if (not world_id) or world_id in VRCHAT_SPECIAL_LOCATION_STRINGS:
                    self.world = None
                else:
                    world = VRChatWorldData.get(world_id)
                    world.subscribe(
                        self.async_schedule_update_ha_state_of_world_entities
                    )
                    self.account.create_task(world.get_data())
                    self.world = world
        except Exception:
            _LOGGER.exception("Error processing user data.")
        finally:
            self._data = new_data
            self.setup_entities()
            self.async_update_entities(force_refresh=True)
            if (device_entry := self.device_entry) is not None:
                self.account.device_registry.async_update_device(
                    device_entry.id,
                    name=new_data.get("displayName"),
                    model=new_data.get("bio"),
                )

    def async_schedule_update_ha_state_of_world_entities(self, *_, **__) -> None:
        """Update entities that subscribe to world updates."""
        self.setup_entities()
        self.async_update_entities(force_refresh=True, world_update=True)

    def async_update_entities(
        self, force_refresh: bool, world_update: bool = False
    ) -> None:
        """Notify added entities about account or world data changes."""
        for listener in self._entity_update_listeners:
            listener(force_refresh, world_update)

    def async_add_entity_update_listener(
        self, listener: Callable[[bool, bool], None]
    ) -> Callable[[], None]:
        """Add an entity update listener."""
        self._entity_update_listeners.append(listener)

        def remove_listener() -> None:
            self._entity_update_listeners.remove(listener)

        return remove_listener

    @property
    def destination_world(self):
        """Destination world."""
        if (traveling_to_world_id := self.data.get("travelingToWorldId")) is not None:
            return VRChatWorldData.get(traveling_to_world_id)
        return None

    @property
    def device_info(self):
        """Device info."""
        data_get = self.data.get
        return self._calculate_device_info(data_get("displayName"), data_get("bio"))

    @cache
    def _calculate_device_info(self, name: str, bio: str):
        user_id = self.data["id"]
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.account.config_entry.unique_id}:{user_id}",
                )
            },
            name=name,
            model=bio,
            configuration_url=VRCHAT_USER_PAGE_BASE_URL + user_id,
        )

    @property
    def device_entry(self):
        """Device entry that represents this user."""
        identifier = next(iter(self.device_info["identifiers"]))
        return self.account.device_registry.async_get_device_by_identifier(
            identifier, self.account.config_entry.entry_id
        )

    @cached_property
    def is_current_user(self):
        "Is current user."
        return self.data["id"] == self.account.current_user_data["id"]

    @cached_property
    def is_not_current_user(self):
        "Is not current user."
        return not self.is_current_user

    async def update_user(self, data: vrchatapi.UpdateUserRequest):
        """Update user info."""
        self.data = await self.account.use_api(
            lambda api: api.update_user(self.data["id"], data)
        )

    def setup_entities(
        self,
        platform: str | None = None,
    ):
        """Setup entities of a specific platform. Or setup all platforms if None is specified. Do nothing if entity has already been setup."""
        if platform is None:
            for p in self.account.add_entities_callback_map:
                self._setup_entities(p)
        else:
            self._setup_entities(platform)

    def _setup_entities(
        self,
        platform: str,
    ):
        if platform not in self.account.add_entities_callback_map:
            return
        add_entities = self.account.add_entities_callback_map[platform]
        for entity_cls in vrchat_user_data_entity_classes_map[platform]:
            if entity_cls not in self.added_entity_map and entity_cls.should_add(self):
                entity = entity_cls(self)
                self.added_entity_map[entity_cls] = entity
                add_entities([entity], update_before_add=True)

    def handle_event(self, data: WebsocketUserEvent):
        """Handle websocket event without awaiting on it."""
        self.account.create_task(self.async_handle_event(data))

    async def async_handle_event(self, data: WebsocketUserEvent):
        """Handle websocket event."""

        old_data = self.data
        content = data.get("content")

        if content is None or content.get("userId") != old_data["id"]:
            return

        event_type = data.get("type")

        if (
            event_type == VRChatWebsocketEventType.FRIEND_DELETE
            and (device_entry := self.device_entry) is not None
        ):
            self.account.device_registry.async_remove_device(device_entry.id)
            await self.close()
            return
        if event_type == VRChatWebsocketEventType.FRIEND_OFFLINE:
            new_data = old_data.copy()
            new_data["location"] = VRChatUserState.OFFLINE
            new_data["worldId"] = VRChatUserState.OFFLINE
            new_data["instanceId"] = VRChatUserState.OFFLINE
            new_data["status"] = VRChatUserState.OFFLINE
            new_data["statusDescription"] = ""
            self.data = new_data
            return
        if (new_data := content.get("user")) is None:
            return
        if event_type == VRChatWebsocketEventType.USER_UPDATE:
            self.data = {**old_data, **new_data}
            return
        extra_data = content.copy()
        extra_data.pop("user", None)
        extra_data.pop("userId", None)
        extra_data.pop("world", None)
        new_data.update(extra_data)
        if "location" not in new_data:
            if event_type == VRChatWebsocketEventType.FRIEND_ACTIVE:
                new_data["location"] = VRChatUserState.OFFLINE
                new_data["worldId"] = VRChatUserState.OFFLINE
                new_data["instanceId"] = VRChatUserState.OFFLINE
            else:
                new_data["location"] = old_data.get("location") or old_data.get(
                    "presence", {}
                ).get("location")
        self.data = new_data

    @override
    def close(self):
        """Close."""
        account = self.account
        account.users.pop(self.data["id"], None)
        account.remove_from_cleanups(self.close)
        if (world := self.world) is not None:
            world.unsubscribe(self.async_schedule_update_ha_state_of_world_entities)
        return super().close()


class VRChatUserDataEntity(Entity):
    """ABC for an entity that represents a VRChat user data point."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    icon_map: dict[Any, str] | None = None

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

    def __init__(self, user: VRChatUserDataCoordinator):
        """Initialization."""
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
    def available(self):
        """Available."""
        return self.user.account.available

    @property
    @override
    def device_info(self):
        """Device info."""
        return self.user.device_info

    @cached_property
    @override
    def unique_id(self):
        """Unique ID."""
        return f"{DOMAIN}.{self.entity_description.key}.{next(iter(self.device_info['identifiers']))[1]}"

    @cached_property
    @override
    def translation_key(self):
        """Translation key."""
        return re.sub(r"(?<!^)(?=[A-Z])", "_", self.entity_description.key).lower()

    @property
    @override
    def icon(self):
        """Return icon from icon map. Fallback to default implementation if not found."""
        if (
            self.icon_map is not None
            and (icon := self.icon_map.get(self.vrchat_user_data_state)) is not None
        ):
            return icon
        return super().icon

    @classmethod
    def get_raw_state_from_user_data(cls, user_data: User, key: str | None = None):
        """Get raw state from user data."""
        if key is None:
            key = cls.entity_description.key
        return user_data.get(key) or user_data.get("presence", {}).get(key)

    @classmethod
    def get_state_from_user_data(cls, user_data: User, key: str | None = None):
        """Get state from user data."""
        state = cls.get_raw_state_from_user_data(user_data, key)
        if isinstance(state, str):
            return process_vrchat_string(state)
        return state

    @property
    def vrchat_user_data_state(self):
        """The state."""
        return self.get_state_from_user_data(self.user.data)

    def vrchat_user_world_data_get[T](self, key: str, default: T | None = None):
        """Get from user world data."""
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
        """Determine whether this entity should be added based on user data."""
        return cls.get_state_from_user_data(user_data) is not None

    @classmethod
    def _register_vrchat_user_data_entity_subclass(cls, platform: str):
        vrchat_user_data_entity_classes_map.setdefault(platform, []).append(cls)


vrchat_user_data_entity_classes_map: dict[str, list[type[VRChatUserDataEntity]]] = {}


class VRChatUserLocationEntityMixin:
    """VRChat user location data entity mixin."""

    subscribe_to_world_update = True

    @classmethod
    def should_add_based_on_user_data(cls, user_data):
        """Should always add user location data."""
        return True

    async def async_update(self):
        """Wait for world data update task if necessary."""

        world: VRChatWorldData | None = self.user.world or self.user.destination_world

        if world is None:
            return
        if world.data is not None:
            return
        if world.task is not None:
            await world.task
