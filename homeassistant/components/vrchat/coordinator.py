"""Adapt library account updates to Home Assistant entities and devices."""

from collections.abc import Callable
import logging

from propcache.api import cached_property
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.highlevel import (
    AccountIdMismatch,
    VRChatAccount,
    VRChatAPI,
    VRChatUser,
    VRChatWorldData,
)
from vrchatapi.highlevel.types import User

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, USER_AGENT, VRCHAT_USER_PAGE_BASE_URL
from .entity import VRChatUserDataEntity, vrchat_user_data_entity_classes_map
from .store import InitialCurrentUserData, get_vrchat_auth_cookie_store

_LOGGER = logging.getLogger(__name__)
type VRChatConfigEntry = ConfigEntry[VRChatAccountDataCoordinator]


class VRChatAccountDataCoordinator:
    """Own the HA lifecycle and translate library notifications."""

    def __init__(self, hass: HomeAssistant, entry: VRChatConfigEntry) -> None:
        """Initialize the integration adapter."""
        self.hass = hass
        self.config_entry = entry
        self.device_registry = dr.async_get(hass)
        assert entry.unique_id is not None
        self.cookie_store = get_vrchat_auth_cookie_store(hass, entry.unique_id)
        self.users: dict[str, VRChatUserDataCoordinator] = {}
        self.add_entities_callback_map: dict[str, AddConfigEntryEntitiesCallback] = {}
        self.client: VRChatAccount | None = None

    @property
    def available(self) -> bool:
        """Return the library connection state."""
        return self.client is not None and self.client.available

    async def async_start(self) -> None:
        """Load credentials and start the account subscription."""
        entry = self.config_entry
        assert entry.unique_id is not None
        api = VRChatAPI(
            entry.data, await self.cookie_store.async_load(), user_agent=USER_AGENT
        )
        self.client = VRChatAccount(
            api,
            entry.unique_id,
            on_user=self._user_updated,
            on_remove=self._user_removed,
            on_available=self._availability_updated,
            on_auth_error=self._auth_error,
            on_authenticated=self._save_cookie,
        )
        try:
            await self.client.start(InitialCurrentUserData.pop(entry.unique_id, None))
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"config_entry_title": entry.title},
            ) from err
        except AccountIdMismatch as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unique_id_mismatch",
                translation_placeholders={
                    "expected_id": err.expected,
                    "got_id": err.actual,
                },
            ) from err
        except Exception as err:
            raise VRChatAccountSetupFailed(entry) from err

    async def _save_cookie(self, api: VRChatAPI) -> None:
        await self.cookie_store.async_save(api.cookie)

    def _user_updated(self, data: VRChatUser, world_update: bool) -> None:
        if (user := self.users.get(data.id)) is None:
            user = self.users[data.id] = VRChatUserDataCoordinator(self, data)
        user.setup_entities()
        user.async_update_entities(force_refresh=True, world_update=world_update)
        if (device := user.device_entry) is not None:
            self.device_registry.async_update_device(
                device.id,
                name=data.data.get("displayName"),
            )

    def _user_removed(self, user_id: str) -> None:
        if (user := self.users.pop(user_id, None)) is not None and (
            device := user.device_entry
        ) is not None:
            self.device_registry.async_remove_device(device.id)

    def _availability_updated(self, available: bool) -> None:
        for user in self.users.values():
            user.async_update_entities(force_refresh=available)

    def _auth_error(self, error: Exception) -> None:
        _LOGGER.error(
            "VRChat authentication expired; reload the entry to sign in again: %s",
            error,
        )

    def setup_entities(
        self, platform: str, add_entities: AddConfigEntryEntitiesCallback
    ) -> None:
        """Register the platform and create entities for existing users."""
        self.add_entities_callback_map[platform] = add_entities
        for user in self.users.values():
            user.setup_entities(platform)

    async def close(self) -> None:
        """Close account connections and background work."""
        if self.client is not None:
            await self.client.close()


class VRChatAccountSetupFailed(ConfigEntryNotReady):
    """Translate account setup failures."""

    def __init__(self, entry: VRChatConfigEntry) -> None:
        """Build the translated setup error."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"config_entry_title": entry.title},
        )


class VRChatUserDataCoordinator:
    """Expose a library user to HA entities."""

    def __init__(self, account: VRChatAccountDataCoordinator, user: VRChatUser) -> None:
        """Initialize entity listeners for a library user."""
        self.account = account
        self.user = user
        self.added_entity_map: dict[
            type[VRChatUserDataEntity], VRChatUserDataEntity
        ] = {}
        self._entity_update_listeners: list[Callable[[bool, bool], None]] = []

    @property
    def data(self) -> User:
        """Return the library user snapshot."""
        return self.user.data

    @property
    def world(self) -> VRChatWorldData | None:
        """Return the current world."""
        return self.user.world

    @property
    def destination_world(self) -> VRChatWorldData | None:
        """Return the destination world."""
        return self.user.destination_world

    def async_update_entities(
        self, force_refresh: bool, world_update: bool = False
    ) -> None:
        """Notify added entities about account or world data changes."""
        for listener in list(self._entity_update_listeners):
            listener(force_refresh, world_update)

    def async_add_entity_update_listener(
        self, listener: Callable[[bool, bool], None]
    ) -> Callable[[], None]:
        """Add an entity update listener."""
        self._entity_update_listeners.append(listener)

        def remove_listener() -> None:
            if listener in self._entity_update_listeners:
                self._entity_update_listeners.remove(listener)

        return remove_listener

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return self._calculate_device_info(self.data.get("displayName"))

    def _calculate_device_info(self, name: str | None) -> DeviceInfo:
        user_id = self.data["id"]
        device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.account.config_entry.unique_id}:{user_id}",
                )
            },
            name=name,
            configuration_url=VRCHAT_USER_PAGE_BASE_URL + user_id,
        )
        if self.is_not_current_user:
            device_info["via_device_id"] = dr.async_get_device_id_by_identifier(
                self.account.hass,
                (
                    DOMAIN,
                    f"{self.account.config_entry.unique_id}:"
                    f"{self.account.config_entry.unique_id}",
                ),
                config_entry_id=self.account.config_entry.entry_id,
            )
        return device_info

    @property
    def device_entry(self) -> dr.DeviceEntry | None:
        """Device entry that represents this user."""
        identifier = next(iter(self.device_info["identifiers"]))
        return self.account.device_registry.async_get_device_by_identifier(
            identifier, self.account.config_entry.entry_id
        )

    @cached_property
    def is_current_user(self) -> bool:
        "Is current user."
        return self.data["id"] == self.account.config_entry.unique_id

    @cached_property
    def is_not_current_user(self) -> bool:
        "Is not current user."
        return not self.is_current_user

    def setup_entities(
        self,
        platform: str | None = None,
    ) -> None:
        """Setup entities of a specific platform. Or setup all platforms if None is specified. Do nothing if entity has already been setup."""
        if platform is None:
            for p in self.account.add_entities_callback_map:
                self._setup_entities(p)
        else:
            self._setup_entities(platform)

    def _setup_entities(
        self,
        platform: str,
    ) -> None:
        if platform not in self.account.add_entities_callback_map:
            return
        add_entities = self.account.add_entities_callback_map[platform]
        for entity_cls in vrchat_user_data_entity_classes_map[platform]:
            if entity_cls not in self.added_entity_map and entity_cls.should_add(self):
                entity = entity_cls(self)
                self.added_entity_map[entity_cls] = entity
                add_entities([entity], update_before_add=True)
