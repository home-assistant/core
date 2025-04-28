"""Preference management for cloud."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any
import uuid

from hass_nabucasa.voice import MAP_VOICE, Gender

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import User
from homeassistant.components import webhook
from homeassistant.components.google_assistant.http import (
    async_get_users as async_get_google_assistant_users,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util.logging import async_create_catching_coro

from .const import (
    DEFAULT_ALEXA_REPORT_STATE,
    DEFAULT_EXPOSED_DOMAINS,
    DEFAULT_GOOGLE_REPORT_STATE,
    DEFAULT_TTS_DEFAULT_VOICE,
    DOMAIN,
    PREF_ALEXA_DEFAULT_EXPOSE,
    PREF_ALEXA_ENTITY_CONFIGS,
    PREF_ALEXA_REPORT_STATE,
    PREF_ALEXA_SETTINGS_VERSION,
    PREF_CLOUD_USER,
    PREF_CLOUDHOOKS,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_CLOUD_ICE_SERVERS,
    PREF_ENABLE_GOOGLE,
    PREF_ENABLE_REMOTE,
    PREF_GOOGLE_CONNECTED,
    PREF_GOOGLE_DEFAULT_EXPOSE,
    PREF_GOOGLE_ENTITY_CONFIGS,
    PREF_GOOGLE_LOCAL_WEBHOOK_ID,
    PREF_GOOGLE_REPORT_STATE,
    PREF_GOOGLE_SECURE_DEVICES_PIN,
    PREF_GOOGLE_SETTINGS_VERSION,
    PREF_INSTANCE_ID,
    PREF_REMOTE_ALLOW_REMOTE_ENABLE,
    PREF_REMOTE_DOMAIN,
    PREF_TTS_DEFAULT_VOICE,
    PREF_USERNAME,
)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 4

ALEXA_SETTINGS_VERSION = 3
GOOGLE_SETTINGS_VERSION = 3


class CloudPreferencesStore(Store):
    """Store cloud preferences."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""

        async def google_connected() -> bool:
            """Return True if our user is preset in the google_assistant store."""
            # If we don't have a user, we can't be connected to Google
            if not (cur_username := old_data.get(PREF_USERNAME)):
                return False

            # If our user is in the Google store, we're connected
            return cur_username in await async_get_google_assistant_users(self.hass)

        if old_major_version == 1:
            if old_minor_version < 2:
                old_data.setdefault(PREF_ALEXA_SETTINGS_VERSION, 1)
                old_data.setdefault(PREF_GOOGLE_SETTINGS_VERSION, 1)
            if old_minor_version < 3:
                # Import settings from the google_assistant store which was previously
                # shared between the cloud integration and manually configured Google
                # assistant.
                # In HA Core 2024.9, remove the import and also remove the Google
                # assistant store if it's not been migrated by manual Google assistant
                old_data.setdefault(PREF_GOOGLE_CONNECTED, await google_connected())
            if old_minor_version < 4:
                # Update the default TTS voice to the new default.
                # The default tts voice is a tuple.
                # The first item is the language, the second item used to be gender.
                # The new second item is the voice name.
                default_tts_voice = old_data.get(PREF_TTS_DEFAULT_VOICE)
                if default_tts_voice and (voice_item_two := default_tts_voice[1]) in (
                    Gender.FEMALE,
                    Gender.MALE,
                ):
                    language: str = default_tts_voice[0]
                    if voice := MAP_VOICE.get((language, voice_item_two)):
                        old_data[PREF_TTS_DEFAULT_VOICE] = (
                            language,
                            voice,
                        )
                    else:
                        old_data[PREF_TTS_DEFAULT_VOICE] = DEFAULT_TTS_DEFAULT_VOICE

        return old_data


class CloudPreferences:
    """Handle cloud preferences."""

    _prefs: dict[str, Any]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize cloud prefs."""
        self._hass = hass
        self._store = CloudPreferencesStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )
        self._listeners: list[
            Callable[[CloudPreferences], Coroutine[Any, Any, None]]
        ] = []
        self.last_updated: set[str] = set()

    async def async_initialize(self) -> None:
        """Finish initializing the preferences."""
        if (prefs := await self._store.async_load()) is None:
            prefs = self._empty_config("")

        self._prefs = prefs

        if PREF_GOOGLE_LOCAL_WEBHOOK_ID not in self._prefs:
            await self._save_prefs(
                {
                    **self._prefs,
                    PREF_GOOGLE_LOCAL_WEBHOOK_ID: webhook.async_generate_id(),
                }
            )
        if PREF_INSTANCE_ID not in self._prefs:
            await self._save_prefs(
                {
                    **self._prefs,
                    PREF_INSTANCE_ID: uuid.uuid4().hex,
                }
            )

    @callback
    def async_listen_updates(
        self, listener: Callable[[CloudPreferences], Coroutine[Any, Any, None]]
    ) -> Callable[[], None]:
        """Listen for updates to the preferences."""

        @callback
        def unsubscribe() -> None:
            """Remove the listener."""
            self._listeners.remove(listener)

        self._listeners.append(listener)

        return unsubscribe

    async def async_update(
        self,
        *,
        alexa_enabled: bool | UndefinedType = UNDEFINED,
        alexa_report_state: bool | UndefinedType = UNDEFINED,
        alexa_settings_version: int | UndefinedType = UNDEFINED,
        cloud_ice_servers_enabled: bool | UndefinedType = UNDEFINED,
        cloud_user: str | UndefinedType = UNDEFINED,
        cloudhooks: dict[str, dict[str, str | bool]] | UndefinedType = UNDEFINED,
        google_connected: bool | UndefinedType = UNDEFINED,
        google_enabled: bool | UndefinedType = UNDEFINED,
        google_report_state: bool | UndefinedType = UNDEFINED,
        google_secure_devices_pin: str | None | UndefinedType = UNDEFINED,
        google_settings_version: int | UndefinedType = UNDEFINED,
        remote_allow_remote_enable: bool | UndefinedType = UNDEFINED,
        remote_domain: str | None | UndefinedType = UNDEFINED,
        remote_enabled: bool | UndefinedType = UNDEFINED,
        tts_default_voice: tuple[str, str] | UndefinedType = UNDEFINED,
    ) -> None:
        """Update user preferences."""
        prefs = {**self._prefs}

        prefs.update(
            {
                key: value
                for key, value in (
                    (PREF_ALEXA_REPORT_STATE, alexa_report_state),
                    (PREF_ALEXA_SETTINGS_VERSION, alexa_settings_version),
                    (PREF_CLOUD_USER, cloud_user),
                    (PREF_CLOUDHOOKS, cloudhooks),
                    (PREF_ENABLE_ALEXA, alexa_enabled),
                    (PREF_ENABLE_CLOUD_ICE_SERVERS, cloud_ice_servers_enabled),
                    (PREF_ENABLE_GOOGLE, google_enabled),
                    (PREF_ENABLE_REMOTE, remote_enabled),
                    (PREF_GOOGLE_CONNECTED, google_connected),
                    (PREF_GOOGLE_REPORT_STATE, google_report_state),
                    (PREF_GOOGLE_SECURE_DEVICES_PIN, google_secure_devices_pin),
                    (PREF_GOOGLE_SETTINGS_VERSION, google_settings_version),
                    (PREF_REMOTE_ALLOW_REMOTE_ENABLE, remote_allow_remote_enable),
                    (PREF_REMOTE_DOMAIN, remote_domain),
                    (PREF_TTS_DEFAULT_VOICE, tts_default_voice),
                )
                if value is not UNDEFINED
            }
        )

        await self._save_prefs(prefs)

    async def async_set_username(self, username: str | None) -> bool:
        """Set the username that is logged in."""
        # Logging out.
        if username is None:
            user = await self._load_cloud_user()

            if user is not None:
                await self._hass.auth.async_remove_user(user)
                await self._save_prefs({**self._prefs, PREF_CLOUD_USER: None})
            return False

        cur_username = self._prefs.get(PREF_USERNAME)

        if cur_username == username:
            return False

        if cur_username is None:
            await self._save_prefs({**self._prefs, PREF_USERNAME: username})
        else:
            await self._save_prefs(self._empty_config(username))

        return True

    async def async_erase_config(self) -> None:
        """Erase the configuration."""
        await self._save_prefs(self._empty_config(""))

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version."""
        return {
            PREF_ALEXA_DEFAULT_EXPOSE: self.alexa_default_expose,
            PREF_ALEXA_REPORT_STATE: self.alexa_report_state,
            PREF_CLOUDHOOKS: self.cloudhooks,
            PREF_ENABLE_ALEXA: self.alexa_enabled,
            PREF_ENABLE_CLOUD_ICE_SERVERS: self.cloud_ice_servers_enabled,
            PREF_ENABLE_GOOGLE: self.google_enabled,
            PREF_ENABLE_REMOTE: self.remote_enabled,
            PREF_GOOGLE_DEFAULT_EXPOSE: self.google_default_expose,
            PREF_GOOGLE_REPORT_STATE: self.google_report_state,
            PREF_GOOGLE_SECURE_DEVICES_PIN: self.google_secure_devices_pin,
            PREF_REMOTE_ALLOW_REMOTE_ENABLE: self.remote_allow_remote_enable,
            PREF_TTS_DEFAULT_VOICE: self.tts_default_voice,
        }

    @property
    def remote_allow_remote_enable(self) -> bool:
        """Return if it's allowed to remotely activate remote."""
        allowed: bool = self._prefs.get(PREF_REMOTE_ALLOW_REMOTE_ENABLE, True)
        return allowed

    @property
    def remote_enabled(self) -> bool:
        """Return if remote is enabled on start."""
        if not self._prefs.get(PREF_ENABLE_REMOTE, False):
            return False

        return True

    @property
    def remote_domain(self) -> str | None:
        """Return remote domain."""
        return self._prefs.get(PREF_REMOTE_DOMAIN)

    @property
    def alexa_enabled(self) -> bool:
        """Return if Alexa is enabled."""
        alexa_enabled: bool = self._prefs[PREF_ENABLE_ALEXA]
        return alexa_enabled

    @property
    def alexa_report_state(self) -> bool:
        """Return if Alexa report state is enabled."""
        return self._prefs.get(PREF_ALEXA_REPORT_STATE, DEFAULT_ALEXA_REPORT_STATE)  # type: ignore[no-any-return]

    @property
    def alexa_default_expose(self) -> list[str] | None:
        """Return array of entity domains that are exposed by default to Alexa.

        Can return None, in which case for backwards should be interpreted as allow all domains.
        """
        return self._prefs.get(PREF_ALEXA_DEFAULT_EXPOSE)

    @property
    def alexa_entity_configs(self) -> dict[str, Any]:
        """Return Alexa Entity configurations."""
        return self._prefs.get(PREF_ALEXA_ENTITY_CONFIGS, {})  # type: ignore[no-any-return]

    @property
    def alexa_settings_version(self) -> int:
        """Return version of Alexa settings."""
        alexa_settings_version: int = self._prefs[PREF_ALEXA_SETTINGS_VERSION]
        return alexa_settings_version

    @property
    def google_enabled(self) -> bool:
        """Return if Google is enabled."""
        google_enabled: bool = self._prefs[PREF_ENABLE_GOOGLE]
        return google_enabled

    @property
    def google_connected(self) -> bool:
        """Return if Google is connected."""
        google_connected: bool = self._prefs[PREF_GOOGLE_CONNECTED]
        return google_connected

    @property
    def google_report_state(self) -> bool:
        """Return if Google report state is enabled."""
        return self._prefs.get(PREF_GOOGLE_REPORT_STATE, DEFAULT_GOOGLE_REPORT_STATE)  # type: ignore[no-any-return]

    @property
    def google_secure_devices_pin(self) -> str | None:
        """Return if Google is allowed to unlock locks."""
        return self._prefs.get(PREF_GOOGLE_SECURE_DEVICES_PIN)

    @property
    def google_entity_configs(self) -> dict[str, dict[str, Any]]:
        """Return Google Entity configurations."""
        return self._prefs.get(PREF_GOOGLE_ENTITY_CONFIGS, {})  # type: ignore[no-any-return]

    @property
    def google_settings_version(self) -> int:
        """Return version of Google settings."""
        google_settings_version: int = self._prefs[PREF_GOOGLE_SETTINGS_VERSION]
        return google_settings_version

    @property
    def google_local_webhook_id(self) -> str:
        """Return Google webhook ID to receive local messages."""
        google_local_webhook_id: str = self._prefs[PREF_GOOGLE_LOCAL_WEBHOOK_ID]
        return google_local_webhook_id

    @property
    def google_default_expose(self) -> list[str] | None:
        """Return array of entity domains that are exposed by default to Google.

        Can return None, in which case for backwards should be interpreted as allow all domains.
        """
        return self._prefs.get(PREF_GOOGLE_DEFAULT_EXPOSE)

    @property
    def cloudhooks(self) -> dict[str, Any]:
        """Return the published cloud webhooks."""
        return self._prefs.get(PREF_CLOUDHOOKS, {})  # type: ignore[no-any-return]

    @property
    def instance_id(self) -> str | None:
        """Return the instance ID."""
        return self._prefs.get(PREF_INSTANCE_ID)

    @property
    def tts_default_voice(self) -> tuple[str, str]:
        """Return the default TTS voice.

        The return value is a tuple of language and voice.
        """
        return self._prefs.get(PREF_TTS_DEFAULT_VOICE, DEFAULT_TTS_DEFAULT_VOICE)  # type: ignore[no-any-return]

    @property
    def cloud_ice_servers_enabled(self) -> bool:
        """Return if cloud ICE servers are enabled."""
        cloud_ice_servers_enabled: bool = self._prefs.get(
            PREF_ENABLE_CLOUD_ICE_SERVERS, True
        )
        return cloud_ice_servers_enabled

    async def get_cloud_user(self) -> str:
        """Return ID of Home Assistant Cloud system user."""
        user = await self._load_cloud_user()

        if user:
            return user.id

        user = await self._hass.auth.async_create_system_user(
            "Home Assistant Cloud", group_ids=[GROUP_ID_ADMIN], local_only=True
        )
        assert user is not None
        await self.async_update(cloud_user=user.id)
        return user.id

    async def _load_cloud_user(self) -> User | None:
        """Load cloud user if available."""
        if (user_id := self._prefs.get(PREF_CLOUD_USER)) is None:
            return None

        # Fetch the user. It can happen that the user no longer exists if
        # an image was restored without restoring the cloud prefs.
        return await self._hass.auth.async_get_user(user_id)

    async def _save_prefs(self, prefs: dict[str, Any]) -> None:
        """Save preferences to disk."""
        self.last_updated = {
            key for key, value in prefs.items() if value != self._prefs.get(key)
        }
        self._prefs = prefs
        await self._store.async_save(self._prefs)

        for listener in self._listeners:
            self._hass.async_create_task(async_create_catching_coro(listener(self)))

    @callback
    @staticmethod
    def _empty_config(username: str) -> dict[str, Any]:
        """Return an empty config."""
        return {
            PREF_ALEXA_DEFAULT_EXPOSE: DEFAULT_EXPOSED_DOMAINS,
            PREF_ALEXA_ENTITY_CONFIGS: {},
            PREF_ALEXA_SETTINGS_VERSION: ALEXA_SETTINGS_VERSION,
            PREF_CLOUD_USER: None,
            PREF_CLOUDHOOKS: {},
            PREF_ENABLE_ALEXA: True,
            PREF_ENABLE_GOOGLE: True,
            PREF_ENABLE_REMOTE: False,
            PREF_ENABLE_CLOUD_ICE_SERVERS: True,
            PREF_GOOGLE_CONNECTED: False,
            PREF_GOOGLE_DEFAULT_EXPOSE: DEFAULT_EXPOSED_DOMAINS,
            PREF_GOOGLE_ENTITY_CONFIGS: {},
            PREF_GOOGLE_SETTINGS_VERSION: GOOGLE_SETTINGS_VERSION,
            PREF_GOOGLE_LOCAL_WEBHOOK_ID: webhook.async_generate_id(),
            PREF_INSTANCE_ID: uuid.uuid4().hex,
            PREF_GOOGLE_SECURE_DEVICES_PIN: None,
            PREF_REMOTE_DOMAIN: None,
            PREF_REMOTE_ALLOW_REMOTE_ENABLE: True,
            PREF_USERNAME: username,
        }
