"""User-managed HTTP configuration store."""

from ipaddress import IPv4Network, IPv6Network, ip_network
import logging
from typing import Any, Final, TypedDict, cast

import voluptuous as vol

from homeassistant.const import SERVER_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_BASE_URL,
    CONF_CORS_ORIGINS,
    CONF_IP_BAN_ENABLED,
    CONF_LOGIN_ATTEMPTS_THRESHOLD,
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    CONF_SSL_PEER_CERTIFICATE,
    CONF_SSL_PROFILE,
    CONF_TRUSTED_PROXIES,
    CONF_USE_X_FORWARDED_FOR,
    CONF_USE_X_FRAME_OPTIONS,
    DEFAULT_CORS,
    DOMAIN,
    NO_LOGIN_ATTEMPT_THRESHOLD,
    SSL_INTERMEDIATE,
    SSL_MODERN,
)


class ConfData(TypedDict, total=False):
    """Typed dict for config data."""

    server_host: list[str]
    server_port: int
    base_url: str
    ssl_certificate: str
    ssl_peer_certificate: str
    ssl_key: str
    cors_allowed_origins: list[str]
    use_x_forwarded_for: bool
    use_x_frame_options: bool
    trusted_proxies: list[IPv4Network | IPv6Network]
    login_attempts_threshold: int
    ip_ban_enabled: bool
    ssl_profile: str


_LOGGER = logging.getLogger(__name__)

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 2

KEY_STABLE: Final = "stable"
KEY_PENDING: Final = "pending"
KEY_YAML_MIGRATION_DONE: Final = "yaml_migration_done"

DATA_STORE: HassKey[HTTPConfigStore] = HassKey(STORAGE_KEY)


def _ip_network_str(value: Any) -> str:
    """Validate the value is a valid IP network and return its string form."""
    return str(ip_network(value))


HTTP_STORAGE_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_SERVER_HOST): vol.All(
            cv.ensure_list, vol.Length(min=1), [cv.string]
        ),
        vol.Optional(CONF_SERVER_PORT, default=SERVER_PORT): cv.port,
        vol.Optional(CONF_SSL_CERTIFICATE): cv.isfile,
        vol.Optional(CONF_SSL_PEER_CERTIFICATE): cv.isfile,
        vol.Optional(CONF_SSL_KEY): cv.isfile,
        vol.Optional(CONF_CORS_ORIGINS, default=DEFAULT_CORS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Inclusive(CONF_USE_X_FORWARDED_FOR, "proxy"): cv.boolean,
        vol.Inclusive(CONF_TRUSTED_PROXIES, "proxy"): vol.All(
            cv.ensure_list, [_ip_network_str]
        ),
        vol.Optional(
            CONF_LOGIN_ATTEMPTS_THRESHOLD, default=NO_LOGIN_ATTEMPT_THRESHOLD
        ): vol.Any(cv.positive_int, NO_LOGIN_ATTEMPT_THRESHOLD),
        vol.Optional(CONF_IP_BAN_ENABLED, default=True): cv.boolean,
        vol.Optional(CONF_SSL_PROFILE, default=SSL_MODERN): vol.In(
            [SSL_INTERMEDIATE, SSL_MODERN]
        ),
        vol.Optional(CONF_USE_X_FRAME_OPTIONS, default=True): cv.boolean,
    }
)
_DEFAULT_CONFIG: Final[ConfData] = cast(ConfData, HTTP_STORAGE_SCHEMA({}))


def yaml_config_to_storage(conf: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated HTTP_SCHEMA config to a JSON-serializable storage dict."""
    storage_conf: dict[str, Any] = dict(conf)
    storage_conf.pop(CONF_BASE_URL, None)
    if CONF_TRUSTED_PROXIES in storage_conf:
        storage_conf[CONF_TRUSTED_PROXIES] = [
            str(network) for network in storage_conf[CONF_TRUSTED_PROXIES]
        ]
    return storage_conf


class _HTTPStoreData(TypedDict):
    """Data structure for HTTP config storage."""

    stable: ConfData
    pending: ConfData | None
    yaml_migration_done: bool


class _HTTPStore(Store[_HTTPStoreData]):
    """Http store."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        if old_major_version == 1:
            # Run the v1 payload through the storage schema so the v2 ``stable``
            # slot is well-formed (all keys present, values normalised) and the
            # load step can rely on direct key access.
            try:
                stable = dict(HTTP_STORAGE_SCHEMA(old_data))
            except vol.Invalid:
                _LOGGER.warning(
                    "Discarding invalid v1 HTTP config during migration; "
                    "falling back to defaults"
                )
                stable = dict(HTTP_STORAGE_SCHEMA({}))
            return {
                KEY_STABLE: stable,
                KEY_PENDING: None,
                KEY_YAML_MIGRATION_DONE: False,
            }
        return old_data


class HTTPConfigStore:
    """Persist HTTP config as a stable/pending pair.

    ``stable`` holds the last config the user confirmed as working;
    ``pending`` holds an unconfirmed config the user wants to try on
    the next start. Normal startup prefers ``pending`` so the new
    config gets exercised; recovery mode falls back to ``stable`` so
    Home Assistant can still come up after a bad config.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._hass = hass
        self._store = _HTTPStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            private=True,
            atomic_writes=True,
        )
        self._stable: ConfData = _DEFAULT_CONFIG
        self._pending: ConfData | None = None
        self._yaml_migration_done = False
        self._loaded = False

    @property
    def stable(self) -> ConfData:
        """Return the last confirmed-working config."""
        return self._stable

    @property
    def pending(self) -> ConfData | None:
        """Return the unconfirmed config awaiting promotion, if any."""
        return self._pending

    @property
    def yaml_migration_done(self) -> bool:
        """Return whether the YAML migration has been completed."""
        return self._yaml_migration_done

    async def async_load(self) -> None:
        """Load the stable and pending configs from disk."""
        if self._loaded:
            return
        raw = await self._store.async_load()
        if raw is not None:
            self._stable = raw[KEY_STABLE]
            self._pending = raw[KEY_PENDING]
            self._yaml_migration_done = raw[KEY_YAML_MIGRATION_DONE]
        self._loaded = True

    async def async_set_pending(self, config: ConfData | None) -> None:
        """Set (or clear) the pending config."""
        await self.async_load()
        if config == self.stable:
            # No need to save a pending config that is the same as stable.
            config = None
        self._pending = config
        await self._async_persist()

    async def async_promote_pending(self) -> None:
        """Promote the pending config to stable.

        Raises ``HomeAssistantError`` if there is nothing to promote.
        """
        await self.async_load()
        if self._pending is None:
            raise HomeAssistantError("No pending HTTP config to promote")
        self._stable = self._pending
        self._pending = None
        await self._async_persist()

    async def async_migrate_yaml(self, config: ConfData) -> None:
        """Migrate YAML config to storage as pending if not the same as the config used for recovery."""
        await self.async_load()
        validated_config = cast(ConfData, HTTP_STORAGE_SCHEMA(config))
        self._pending = None if validated_config == self._stable else validated_config
        self._yaml_migration_done = True
        await self._async_persist()

    async def _async_persist(self) -> None:
        """Write the current state to disk (or remove the file if empty)."""
        await self._store.async_save(
            {
                KEY_STABLE: self._stable,
                KEY_PENDING: self._pending,
                KEY_YAML_MIGRATION_DONE: self._yaml_migration_done,
            }
        )


async def async_get_and_load_store(hass: HomeAssistant) -> HTTPConfigStore:
    """Return the singleton HTTP config store and load it."""
    if (store := hass.data.get(DATA_STORE)) is None:
        store = HTTPConfigStore(hass)
        hass.data[DATA_STORE] = store
    await store.async_load()
    return store


async def async_load_config(hass: HomeAssistant, config: ConfigType) -> ConfData:
    """Load the HTTP config to apply on this startup.

    YAML config is only migrated once. Subsequent boots will ignore YAML and
    use the store exclusively.

    Resolution order:
    - Recovery mode: always use ``stable`` so HA stays reachable after a bad
      config; YAML is ignored entirely (any pending YAML migration is
      deferred to the next normal boot).
    - Normal mode: prefer ``pending`` if set, otherwise ``stable``.
    """
    store = await async_get_and_load_store(hass)
    if hass.config.recovery_mode:
        _LOGGER.info("Recovery mode active; using stable HTTP config")
        return store.stable

    yaml_conf: ConfData | None = config.get(DOMAIN)
    if store.yaml_migration_done:
        if yaml_conf is not None:
            # YAML is still present after migration completed; surface a repair
            # issue so the user knows their YAML is being ignored.
            ir.async_create_issue(
                hass,
                DOMAIN,
                "yaml_still_present_after_migration",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="yaml_still_present_after_migration",
            )
        else:
            # Clear any leftover deprecation issues if YAML was removed after migration.
            ir.async_delete_issue(hass, DOMAIN, "deprecated_yaml_import_error")
            ir.async_delete_issue(hass, DOMAIN, "deprecated_yaml")
            ir.async_delete_issue(hass, DOMAIN, "yaml_still_present_after_migration")
    else:
        # Migrate YAML to storage and use it directly for this start. The
        # migration function also marks the migration as done so future
        # starts will ignore any remaining YAML.
        conf_in_yaml = yaml_conf is not None
        if yaml_conf is None:
            yaml_conf = cast(ConfData, HTTP_STORAGE_SCHEMA({}))

        try:
            await store.async_migrate_yaml(yaml_conf)
        except Exception:
            _LOGGER.exception("Failed to migrate HTTP YAML configuration to storage")
            ir.async_create_issue(
                hass,
                DOMAIN,
                "deprecated_yaml_import_error",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="deprecated_yaml_import_error",
            )
        else:
            if conf_in_yaml:
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "deprecated_yaml",
                    breaks_in_ha_version="2027.6.0",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                )

    if store.pending is not None:
        _LOGGER.info("Using pending HTTP config")
        return store.pending

    _LOGGER.info("Using stable HTTP config")
    return store.stable
