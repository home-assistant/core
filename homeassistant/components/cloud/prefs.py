"""Preference management for cloud."""
from __future__ import annotations

from ipaddress import ip_address

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import User
from homeassistant.core import callback
from homeassistant.helpers.typing import UNDEFINED
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
    PREF_ALIASES,
    PREF_CLOUD_USER,
    PREF_CLOUDHOOKS,
    PREF_DISABLE_2FA,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_GOOGLE,
    PREF_ENABLE_REMOTE,
    PREF_GOOGLE_DEFAULT_EXPOSE,
    PREF_GOOGLE_ENTITY_CONFIGS,
    PREF_GOOGLE_LOCAL_WEBHOOK_ID,
    PREF_GOOGLE_REPORT_STATE,
    PREF_GOOGLE_SECURE_DEVICES_PIN,
    PREF_OVERRIDE_NAME,
    PREF_SHOULD_EXPOSE,
    PREF_TTS_DEFAULT_VOICE,
    PREF_USERNAME,
    InvalidTrustedNetworks,
    InvalidTrustedProxies,
)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


class CloudPreferences:
    """Handle cloud preferences."""

    def __init__(self, hass):
        """Initialize cloud prefs."""
        self._hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._prefs = None
        self._listeners = []

    async def async_initialize(self):
        """Finish initializing the preferences."""
        prefs = await self._store.async_load()

        if prefs is None:
            prefs = self._empty_config("")

        self._prefs = prefs

        if PREF_GOOGLE_LOCAL_WEBHOOK_ID not in self._prefs:
            await self._save_prefs(
                {
                    **self._prefs,
                    PREF_GOOGLE_LOCAL_WEBHOOK_ID: self._hass.components.webhook.async_generate_id(),
                }
            )

    @callback
    def async_listen_updates(self, listener):
        """Listen for updates to the preferences."""
        self._listeners.append(listener)

    async def async_update(
        self,
        *,
        google_enabled=UNDEFINED,
        alexa_enabled=UNDEFINED,
        remote_enabled=UNDEFINED,
        google_secure_devices_pin=UNDEFINED,
        cloudhooks=UNDEFINED,
        cloud_user=UNDEFINED,
        google_entity_configs=UNDEFINED,
        alexa_entity_configs=UNDEFINED,
        alexa_report_state=UNDEFINED,
        google_report_state=UNDEFINED,
        alexa_default_expose=UNDEFINED,
        google_default_expose=UNDEFINED,
        tts_default_voice=UNDEFINED,
    ):
        """Update user preferences."""
        prefs = {**self._prefs}

        for key, value in (
            (PREF_ENABLE_GOOGLE, google_enabled),
            (PREF_ENABLE_ALEXA, alexa_enabled),
            (PREF_ENABLE_REMOTE, remote_enabled),
            (PREF_GOOGLE_SECURE_DEVICES_PIN, google_secure_devices_pin),
            (PREF_CLOUDHOOKS, cloudhooks),
            (PREF_CLOUD_USER, cloud_user),
            (PREF_GOOGLE_ENTITY_CONFIGS, google_entity_configs),
            (PREF_ALEXA_ENTITY_CONFIGS, alexa_entity_configs),
            (PREF_ALEXA_REPORT_STATE, alexa_report_state),
            (PREF_GOOGLE_REPORT_STATE, google_report_state),
            (PREF_ALEXA_DEFAULT_EXPOSE, alexa_default_expose),
            (PREF_GOOGLE_DEFAULT_EXPOSE, google_default_expose),
            (PREF_TTS_DEFAULT_VOICE, tts_default_voice),
        ):
            if value is not UNDEFINED:
                prefs[key] = value

        if remote_enabled is True and self._has_local_trusted_network:
            prefs[PREF_ENABLE_REMOTE] = False
            raise InvalidTrustedNetworks

        if remote_enabled is True and self._has_local_trusted_proxies:
            prefs[PREF_ENABLE_REMOTE] = False
            raise InvalidTrustedProxies

        await self._save_prefs(prefs)

    async def async_update_google_entity_config(
        self,
        *,
        entity_id,
        override_name=UNDEFINED,
        disable_2fa=UNDEFINED,
        aliases=UNDEFINED,
        should_expose=UNDEFINED,
    ):
        """Update config for a Google entity."""
        entities = self.google_entity_configs
        entity = entities.get(entity_id, {})

        changes = {}
        for key, value in (
            (PREF_OVERRIDE_NAME, override_name),
            (PREF_DISABLE_2FA, disable_2fa),
            (PREF_ALIASES, aliases),
            (PREF_SHOULD_EXPOSE, should_expose),
        ):
            if value is not UNDEFINED:
                changes[key] = value

        if not changes:
            return

        updated_entity = {**entity, **changes}

        updated_entities = {**entities, entity_id: updated_entity}
        await self.async_update(google_entity_configs=updated_entities)

    async def async_update_alexa_entity_config(
        self, *, entity_id, should_expose=UNDEFINED
    ):
        """Update config for an Alexa entity."""
        entities = self.alexa_entity_configs
        entity = entities.get(entity_id, {})

        changes = {}
        for key, value in ((PREF_SHOULD_EXPOSE, should_expose),):
            if value is not UNDEFINED:
                changes[key] = value

        if not changes:
            return

        updated_entity = {**entity, **changes}

        updated_entities = {**entities, entity_id: updated_entity}
        await self.async_update(alexa_entity_configs=updated_entities)

    async def async_set_username(self, username) -> bool:
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

    def as_dict(self):
        """Return dictionary version."""
        return {
            PREF_ALEXA_DEFAULT_EXPOSE: self.alexa_default_expose,
            PREF_ALEXA_ENTITY_CONFIGS: self.alexa_entity_configs,
            PREF_ALEXA_REPORT_STATE: self.alexa_report_state,
            PREF_CLOUDHOOKS: self.cloudhooks,
            PREF_ENABLE_ALEXA: self.alexa_enabled,
            PREF_ENABLE_GOOGLE: self.google_enabled,
            PREF_ENABLE_REMOTE: self.remote_enabled,
            PREF_GOOGLE_DEFAULT_EXPOSE: self.google_default_expose,
            PREF_GOOGLE_ENTITY_CONFIGS: self.google_entity_configs,
            PREF_GOOGLE_REPORT_STATE: self.google_report_state,
            PREF_GOOGLE_SECURE_DEVICES_PIN: self.google_secure_devices_pin,
            PREF_TTS_DEFAULT_VOICE: self.tts_default_voice,
        }

    @property
    def remote_enabled(self):
        """Return if remote is enabled on start."""
        enabled = self._prefs.get(PREF_ENABLE_REMOTE, False)

        if not enabled:
            return False

        if self._has_local_trusted_network or self._has_local_trusted_proxies:
            return False

        return True

    @property
    def alexa_enabled(self):
        """Return if Alexa is enabled."""
        return self._prefs[PREF_ENABLE_ALEXA]

    @property
    def alexa_report_state(self):
        """Return if Alexa report state is enabled."""
        return self._prefs.get(PREF_ALEXA_REPORT_STATE, DEFAULT_ALEXA_REPORT_STATE)

    @property
    def alexa_default_expose(self) -> list[str] | None:
        """Return array of entity domains that are exposed by default to Alexa.

        Can return None, in which case for backwards should be interpreted as allow all domains.
        """
        return self._prefs.get(PREF_ALEXA_DEFAULT_EXPOSE)

    @property
    def alexa_entity_configs(self):
        """Return Alexa Entity configurations."""
        return self._prefs.get(PREF_ALEXA_ENTITY_CONFIGS, {})

    @property
    def google_enabled(self):
        """Return if Google is enabled."""
        return self._prefs[PREF_ENABLE_GOOGLE]

    @property
    def google_report_state(self):
        """Return if Google report state is enabled."""
        return self._prefs.get(PREF_GOOGLE_REPORT_STATE, DEFAULT_GOOGLE_REPORT_STATE)

    @property
    def google_secure_devices_pin(self):
        """Return if Google is allowed to unlock locks."""
        return self._prefs.get(PREF_GOOGLE_SECURE_DEVICES_PIN)

    @property
    def google_entity_configs(self):
        """Return Google Entity configurations."""
        return self._prefs.get(PREF_GOOGLE_ENTITY_CONFIGS, {})

    @property
    def google_local_webhook_id(self):
        """Return Google webhook ID to receive local messages."""
        return self._prefs[PREF_GOOGLE_LOCAL_WEBHOOK_ID]

    @property
    def google_default_expose(self) -> list[str] | None:
        """Return array of entity domains that are exposed by default to Google.

        Can return None, in which case for backwards should be interpreted as allow all domains.
        """
        return self._prefs.get(PREF_GOOGLE_DEFAULT_EXPOSE)

    @property
    def cloudhooks(self):
        """Return the published cloud webhooks."""
        return self._prefs.get(PREF_CLOUDHOOKS, {})

    @property
    def tts_default_voice(self):
        """Return the default TTS voice."""
        return self._prefs.get(PREF_TTS_DEFAULT_VOICE, DEFAULT_TTS_DEFAULT_VOICE)

    async def get_cloud_user(self) -> str:
        """Return ID from Home Assistant Cloud system user."""
        user = await self._load_cloud_user()

        if user:
            return user.id

        user = await self._hass.auth.async_create_system_user(
            "Home Assistant Cloud", [GROUP_ID_ADMIN]
        )
        await self.async_update(cloud_user=user.id)
        return user.id

    async def _load_cloud_user(self) -> User | None:
        """Load cloud user if available."""
        user_id = self._prefs.get(PREF_CLOUD_USER)

        if user_id is None:
            return None

        # Fetch the user. It can happen that the user no longer exists if
        # an image was restored without restoring the cloud prefs.
        return await self._hass.auth.async_get_user(user_id)

    @property
    def _has_local_trusted_network(self) -> bool:
        """Return if we allow localhost to bypass auth."""
        local4 = ip_address("127.0.0.1")
        local6 = ip_address("::1")

        for prv in self._hass.auth.auth_providers:
            if prv.type != "trusted_networks":
                continue

            for network in prv.trusted_networks:
                if local4 in network or local6 in network:
                    return True

        return False

    @property
    def _has_local_trusted_proxies(self) -> bool:
        """Return if we allow localhost to be a proxy and use its data."""
        if not hasattr(self._hass, "http"):
            return False

        local4 = ip_address("127.0.0.1")
        local6 = ip_address("::1")

        if any(
            local4 in nwk or local6 in nwk for nwk in self._hass.http.trusted_proxies
        ):
            return True

        return False

    async def _save_prefs(self, prefs):
        """Save preferences to disk."""
        self._prefs = prefs
        await self._store.async_save(self._prefs)

        for listener in self._listeners:
            self._hass.async_create_task(async_create_catching_coro(listener(self)))

    @callback
    def _empty_config(self, username):
        """Return an empty config."""
        return {
            PREF_ALEXA_DEFAULT_EXPOSE: DEFAULT_EXPOSED_DOMAINS,
            PREF_ALEXA_ENTITY_CONFIGS: {},
            PREF_CLOUD_USER: None,
            PREF_CLOUDHOOKS: {},
            PREF_ENABLE_ALEXA: True,
            PREF_ENABLE_GOOGLE: True,
            PREF_ENABLE_REMOTE: False,
            PREF_GOOGLE_DEFAULT_EXPOSE: DEFAULT_EXPOSED_DOMAINS,
            PREF_GOOGLE_ENTITY_CONFIGS: {},
            PREF_GOOGLE_LOCAL_WEBHOOK_ID: self._hass.components.webhook.async_generate_id(),
            PREF_GOOGLE_SECURE_DEVICES_PIN: None,
            PREF_USERNAME: username,
        }
