"""Adapt library account updates to Home Assistant entities and devices."""

import logging

from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.highlevel import AccountIdMismatch, VRChatAccount, VRChatAPI, VRChatUser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, USER_AGENT
from .store import InitialCurrentUserData, get_vrchat_auth_cookie_store

_LOGGER = logging.getLogger(__name__)
type VRChatConfigEntry = ConfigEntry[VRChatAccountDataCoordinator]


class VRChatAccountDataCoordinator(DataUpdateCoordinator[dict[str, VRChatUser]]):
    """Own the HA lifecycle and translate library notifications."""

    config_entry: VRChatConfigEntry

    def __init__(self, hass: HomeAssistant, entry: VRChatConfigEntry) -> None:
        """Initialize the integration adapter."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.data = {}
        self.updated_user_id: str | None = None
        self.world_update = False
        self.force_refresh = False
        self.device_registry = dr.async_get(hass)
        assert entry.unique_id is not None
        self.cookie_store = get_vrchat_auth_cookie_store(hass, entry.unique_id)
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
        self.data = self.client.users
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

    @callback
    def _user_updated(self, data: VRChatUser, world_update: bool) -> None:
        self.updated_user_id = data.id
        self.world_update = world_update
        self.force_refresh = True
        self.async_set_updated_data(self.data)
        if (device := self._device_entry(data.id)) is not None:
            self.device_registry.async_update_device(
                device.id,
                name=data.data.get("displayName"),
            )

    @callback
    def _user_removed(self, user_id: str) -> None:
        if (device := self._device_entry(user_id)) is not None:
            self.device_registry.async_remove_device(device.id)
        self.updated_user_id = user_id
        self.world_update = False
        self.force_refresh = False
        self.async_set_updated_data(self.data)

    @callback
    def _availability_updated(self, available: bool) -> None:
        self.updated_user_id = None
        self.world_update = False
        self.force_refresh = available
        self.async_update_listeners()

    @callback
    def _device_entry(self, user_id: str) -> dr.DeviceEntry | None:
        return self.device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{self.config_entry.unique_id}:{user_id}"),
            self.config_entry.entry_id,
        )

    def _auth_error(self, error: Exception) -> None:
        _LOGGER.error(
            "VRChat authentication expired; reload the entry to sign in again: %s",
            error,
        )

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
