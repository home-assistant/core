"""User-managed HTTP configuration store."""

import asyncio
from datetime import datetime, timedelta
from enum import StrEnum
from ipaddress import ip_network
import logging
import os
from typing import Any, Final, TypedDict, cast, override

import voluptuous as vol

from homeassistant.const import CONF_ERROR, SERVER_PORT
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
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
    ENV_SETUP_PORT,
    NO_LOGIN_ATTEMPT_THRESHOLD,
    SSL_INTERMEDIATE,
    SSL_MODERN,
)

_LOGGER = logging.getLogger(__name__)


def default_server_port() -> int:
    """Return the default HTTP server port.

    The built-in default port can be overridden via the
    ``SETUP_PORT`` environment variable. An invalid value is ignored in favor
    of the built-in default.
    """
    if (env_value := os.environ.get(ENV_SETUP_PORT)) is None:
        return SERVER_PORT
    try:
        return cast(int, cv.port(env_value))
    except vol.Invalid:
        _LOGGER.warning(
            "Invalid port %r in %s environment variable; falling back to %s",
            env_value,
            ENV_SETUP_PORT,
            SERVER_PORT,
        )
        return SERVER_PORT


STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 2
STORAGE_MINOR_VERSION: Final = 2

KEY_STABLE: Final = "stable"
KEY_PENDING: Final = "pending"
KEY_YAML_MIGRATION_DONE: Final = "yaml_migration_done"

AUTO_REVERT_DELAY: Final = timedelta(minutes=5)
CONF_CREATED_AT: Final = "created_at"
ERROR_NOT_PROMOTED: Final = "not_promoted"

DATA_STORE: HassKey[HTTPConfigStore] = HassKey(STORAGE_KEY)


class ConfData(TypedDict, total=False):
    """Typed dict for the validated HTTP config (matches ``HTTP_STORAGE_SCHEMA``)."""

    server_host: list[str]
    server_port: int
    ssl_certificate: str
    ssl_peer_certificate: str
    ssl_key: str
    cors_allowed_origins: list[str]
    use_x_forwarded_for: bool
    trusted_proxies: list[str]
    login_attempts_threshold: int
    ip_ban_enabled: bool
    ssl_profile: str
    use_x_frame_options: bool
    created_at: datetime
    error: str | None


class ActiveConfigType(StrEnum):
    """The config slot the running HTTP server was started with."""

    STABLE = "stable"
    PENDING = "pending"
    DEFAULT = "default"


class _HTTPStoreData(TypedDict):
    """Data structure for HTTP config storage."""

    stable: ConfData
    pending: ConfData | None
    yaml_migration_done: bool


def _ip_network_str(value: Any) -> str:
    """Validate the value is a valid IP network and return its string form."""
    return str(ip_network(value))


HTTP_STORAGE_SCHEMA: Final = vol.Schema(
    {
        # YAML used to allow base_url (deprecated); strip it on the way in so
        # the stored config never contains it.
        vol.Remove(CONF_BASE_URL): object,
        vol.Optional(CONF_SERVER_HOST): vol.All(
            cv.ensure_list, vol.Length(min=1), [cv.string]
        ),
        vol.Optional(CONF_SERVER_PORT, default=default_server_port): cv.port,
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
_DEFAULT_CONFIG: Final[ConfData] = ConfData(
    **HTTP_STORAGE_SCHEMA({}), created_at=dt_util.utcnow(), error=None
)


def _strip_meta(config: ConfData) -> ConfData:
    """Return the config without its created_at/error metadata."""
    return cast(
        ConfData,
        {k: v for k, v in config.items() if k not in (CONF_CREATED_AT, CONF_ERROR)},
    )


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
    conf = await store.get_config()
    if hass.config.recovery_mode:
        _LOGGER.info("Recovery mode active; using stable HTTP config")
        return conf

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
            conf = await store.async_migrate_yaml(yaml_conf)
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

    if store.active_config_type is ActiveConfigType.PENDING:
        _LOGGER.info("Using pending HTTP config")
        store.async_schedule_revert_to_stable()
    else:
        _LOGGER.info("Using stable HTTP config")
    return conf


async def async_get_and_load_store(hass: HomeAssistant) -> HTTPConfigStore:
    """Return the singleton HTTP config store and load it."""
    if (store := hass.data.get(DATA_STORE)) is None:
        store = HTTPConfigStore(hass)
        hass.data[DATA_STORE] = store
    await store.async_load()
    return store


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
            minor_version=STORAGE_MINOR_VERSION,
            private=True,
            atomic_writes=True,
        )
        # Copied so recording an error on stable never mutates the shared default.
        self._stable: ConfData = _DEFAULT_CONFIG.copy()
        self._pending: ConfData | None = None
        self._active_config_type: ActiveConfigType = ActiveConfigType.DEFAULT
        self._yaml_migration_done = False
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._revert_unsub: CALLBACK_TYPE | None = None
        self._revert_deadline: datetime | None = None

    @property
    def stable(self) -> ConfData:
        """Return the last confirmed-working config."""
        return self._stable

    @property
    def pending(self) -> ConfData | None:
        """Return the unconfirmed config awaiting promotion, if any."""
        return self._pending

    @property
    def default(self) -> ConfData:
        """Return the built-in default config."""
        return _DEFAULT_CONFIG

    @property
    def active_config_type(self) -> ActiveConfigType:
        """Return the slot the running server was started with, if setup ran."""
        return self._active_config_type

    @property
    def revert_deadline(self) -> datetime | None:
        """Return when the pending config auto-reverts to stable, if scheduled."""
        return self._revert_deadline

    @property
    def yaml_migration_done(self) -> bool:
        """Return whether the YAML migration has been completed."""
        return self._yaml_migration_done

    async def async_load(self) -> None:
        """Load the stable and pending configs from disk."""
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                # Another coroutine may have loaded the config while we were waiting
                # for the lock; check again to avoid unnecessary disk I/O.
                return  # type: ignore[unreachable]
            raw = await self._store.async_load()
            if raw is not None:
                self._stable = raw[KEY_STABLE]
                self._pending = raw[KEY_PENDING]
                self._yaml_migration_done = raw[KEY_YAML_MIGRATION_DONE]
            self._loaded = True

    async def async_set_pending(self, config: ConfData | None) -> None:
        """Set (or clear) the pending config."""
        await self.async_load()
        if config is not None and _strip_meta(config) == _strip_meta(self._stable):
            # No need to save a pending config that is the same as stable.
            config = None
        if (
            config is not None
            and self._pending is not None
            and self._pending[CONF_ERROR] is None
            and _strip_meta(config) == _strip_meta(self._pending)
        ):
            return
        self._pending = config
        if self._pending is not None:
            self._pending[CONF_CREATED_AT] = dt_util.utcnow()
            self._pending[CONF_ERROR] = None
        await self._async_persist()

    async def async_promote_pending(self) -> None:
        """Promote the pending config to stable.

        Raises ``HomeAssistantError`` if there is nothing to promote.
        """
        await self.async_load()
        if self._pending is None:
            raise HomeAssistantError("No pending HTTP config to promote")
        if self._pending[CONF_ERROR] is not None:
            raise HomeAssistantError(
                f"Cannot promote pending HTTP config with error: {self._pending[CONF_ERROR]}"
            )
        self._stable = self._pending
        self._pending = None
        if self._active_config_type is ActiveConfigType.PENDING:
            # The running config now lives in the stable slot.
            self._active_config_type = ActiveConfigType.STABLE
        # The config is now confirmed; no need to revert it anymore.
        self.async_cancel_revert()
        await self._async_persist()

    @callback
    def async_schedule_revert_to_stable(self) -> None:
        """Schedule reverting the pending config back to stable.

        Loading a pending config is a trial. If the user does not promote it
        within ``AUTO_REVERT_DELAY`` (e.g. because the new config made Home
        Assistant unreachable), automatically clear it and restart so the last
        known-good stable config is restored.
        """
        self.async_cancel_revert()
        self._revert_deadline = dt_util.utcnow() + AUTO_REVERT_DELAY
        self._revert_unsub = async_call_later(
            self._hass,
            AUTO_REVERT_DELAY,
            HassJob(
                self._async_revert_to_stable,
                "http config auto-revert",
                cancel_on_shutdown=True,
            ),
        )

    @callback
    def async_cancel_revert(self) -> None:
        """Cancel a scheduled revert, if any.

        Also clears the deadline so ``revert_deadline`` no longer reports a
        revert that will not happen (e.g. after the config is promoted).
        """
        if self._revert_unsub is not None:
            self._revert_unsub()
            self._revert_unsub = None
        self._revert_deadline = None

    async def _async_revert_to_stable(self, _now: datetime) -> None:
        """Mark the unconfirmed pending config reverted and restart to apply stable."""
        self.async_cancel_revert()
        if self._pending is None:
            return
        _LOGGER.warning(
            "Pending HTTP config was not confirmed within %s; reverting to the "
            "stable config and restarting",
            AUTO_REVERT_DELAY,
        )
        self._pending[CONF_ERROR] = ERROR_NOT_PROMOTED
        await self._async_persist()
        # Imported here to avoid a circular import at module load time.
        from homeassistant.components.homeassistant import (  # noqa: PLC0415
            DOMAIN as HASS_DOMAIN,
            SERVICE_HOMEASSISTANT_RESTART,
        )

        await self._hass.services.async_call(HASS_DOMAIN, SERVICE_HOMEASSISTANT_RESTART)

    async def async_migrate_yaml(self, config: ConfData) -> ConfData:
        """Migrate YAML config to storage as pending if not the same as the config used for recovery."""
        await self.async_load()
        validated_config = cast(ConfData, HTTP_STORAGE_SCHEMA(config))
        if self._stable_differs_only_by_lost_proxy_masks(validated_config):
            # Releases up to 2026.7.1 dropped the network mask when storing
            # trusted proxies, and the v1->v2 store migration turned those
            # into host networks (e.g. 10.0.0.0/24 -> 10.0.0.0 -> 10.0.0.0/32).
            # If the YAML config matches stable apart from those lost masks,
            # the user changed nothing: restore the masks in stable instead of
            # staging the YAML as pending.
            self._stable = ConfData(
                **validated_config,
                created_at=self._stable[CONF_CREATED_AT],
                error=None,
            )
        self._pending = None
        if validated_config != _strip_meta(self._stable):
            self._pending = ConfData(
                **validated_config, created_at=dt_util.utcnow(), error=None
            )
        self._yaml_migration_done = True
        await self._async_persist()
        self._active_config_type = (
            ActiveConfigType.PENDING
            if self._pending is not None
            else ActiveConfigType.STABLE
        )
        return validated_config

    def _stable_differs_only_by_lost_proxy_masks(self, config: ConfData) -> bool:
        """Return True if stable equals ``config`` with the trusted proxy masks lost.

        "Lost" means each proxy was reduced to the host network of its network
        address, the shape the old storage bug produced.
        """
        if (proxies := config.get(CONF_TRUSTED_PROXIES)) is None:
            return False
        return _strip_meta(self._stable) == {
            **config,
            CONF_TRUSTED_PROXIES: [
                _ip_network_str(ip_network(proxy).network_address) for proxy in proxies
            ],
        }

    async def _async_persist(self) -> None:
        """Write the current state to disk (or remove the file if empty)."""
        # An error on the confirmed-working stable config is transient;
        # never persist it.
        self._stable[CONF_ERROR] = None
        await self._store.async_save(
            {
                KEY_STABLE: self._stable,
                KEY_PENDING: self._pending,
                KEY_YAML_MIGRATION_DONE: self._yaml_migration_done,
            }
        )

    async def get_config(self) -> ConfData:
        """Resolve the config to use and record it as the active slot.

        Normal mode prefers ``pending`` over ``stable``, unless an error is
        recorded on the pending config (it already failed a trial); recovery
        mode always uses ``stable``.
        """
        await self.async_load()
        pending = self._pending
        if (
            not self._hass.config.recovery_mode
            and pending is not None
            and pending[CONF_ERROR] is None
        ):
            self._active_config_type = ActiveConfigType.PENDING
            return pending
        self._active_config_type = ActiveConfigType.STABLE
        return self._stable

    async def async_get_fallback_config(
        self,
        err: HomeAssistantError | OSError,
    ) -> ConfData:
        """Return the next config to try after the active one could not be applied.

        Implements the fallback chain pending -> stable -> default config, where
        the last step is only taken in recovery mode. Raises when there is no
        (acceptable) fallback left, failing setup: on a normal boot this
        activates recovery mode, in recovery mode it makes the failure visible
        to the outside (e.g. the Supervisor rolls back a Core update whose API
        does not come up).
        """
        failed_type = self._active_config_type
        if failed_type is ActiveConfigType.DEFAULT:
            # Never record the error on the shared default config.
            failed_config = _DEFAULT_CONFIG
        else:
            failed_config = await self.get_config()
            failed_config[CONF_ERROR] = str(err)

        if failed_type is ActiveConfigType.PENDING:
            # An unconfirmed pending config is under trial and cannot even be
            # applied, so it is known to be bad: record the error on it, revert
            # to the stable config right away and continue this same start with
            # it, instead of waiting out the trial window and restarting.
            _LOGGER.error(
                "The new HTTP configuration could not be applied, reverting to "
                "the previous configuration: %s",
                err,
            )
            self.async_cancel_revert()
            # Store the pending config with the error to prevent it from being used again.
            await self._async_persist()
            self._active_config_type = ActiveConfigType.STABLE
            return self._stable

        if (
            # In normal mode, fail setup so recovery mode can take over with a
            # reachable configuration.
            not self._hass.config.recovery_mode
            # The chain is exhausted; nothing left to fall back to.
            or failed_type is ActiveConfigType.DEFAULT
            # With peer certificate verification configured, connections must
            # never be accepted without a verified client certificate; there is
            # no acceptable fallback config.
            or CONF_SSL_PEER_CERTIFICATE in failed_config
        ):
            # An unusable SSL configuration already carries a descriptive
            # HomeAssistantError.
            if isinstance(err, HomeAssistantError):
                raise err
            raise HomeAssistantError(
                f"Failed to create HTTP server at port {failed_config[CONF_SERVER_PORT]}: {err}"
            ) from err

        # The config cannot be applied in recovery mode; fall back to the
        # default config so the recovery UI stays reachable.
        _LOGGER.error(
            "The HTTP configuration could not be applied in recovery mode, "
            "falling back to the default configuration: %s",
            err,
        )
        self._active_config_type = ActiveConfigType.DEFAULT
        return _DEFAULT_CONFIG


class _HTTPStore(Store[_HTTPStoreData]):
    """Http store."""

    @override
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
                stable = HTTP_STORAGE_SCHEMA(old_data)
            except vol.Invalid:
                _LOGGER.warning(
                    "Discarding invalid v1 HTTP config during migration; "
                    "falling back to defaults"
                )
                stable = _DEFAULT_CONFIG
            old_data = {
                KEY_STABLE: stable,
                KEY_PENDING: None,
                KEY_YAML_MIGRATION_DONE: False,
            }
        if old_minor_version < 2:
            # 2.2 added `error` and `created_at` to the config slots
            old_data[KEY_STABLE] = {
                **old_data[KEY_STABLE],
                CONF_CREATED_AT: dt_util.utcnow(),
                CONF_ERROR: None,
            }
            if old_data[KEY_PENDING] is not None:
                old_data[KEY_PENDING] = {
                    **old_data[KEY_PENDING],
                    CONF_CREATED_AT: dt_util.utcnow(),
                    CONF_ERROR: None,
                }
        return old_data
