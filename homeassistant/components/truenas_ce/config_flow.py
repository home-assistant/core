"""Config flow to configure TrueNAS."""

from collections.abc import Mapping
import contextlib
from logging import getLogger
import re
import socket
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import TrueNASAPI
from .const import (
    ALLOWED_DATA_UNITS,
    CONF_CRONJOB_SKIP_DISABLED,
    CONF_DATA_UNIT,
    CONF_SYSTEM_ID,
    DEFAULT_CRONJOB_SKIP_DISABLED,
    DEFAULT_DATA_UNIT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_HOST,
    DEFAULT_SSL_VERIFY,
    DOMAIN,
    ERR_API_NOT_FOUND,
    ERR_CERT_VERIFY_FAILED,
    ERR_CONNECTION_REFUSED,
    ERR_HANDSHAKE_TIMEOUT,
    ERR_HTTP_USED,
    ERR_INVALID_HOSTNAME,
    ERR_INVALID_KEY,
    ERR_MALFORMED_RESULT,
    ERR_PROXY_INTERCEPTED,
    ERR_TLS_NOT_SUPPORTED,
    ERR_UNKNOWN_HOSTNAME,
    ERR_WS_NOT_SUPPORTED,
    KNOWN_DOMAINS,
    LEGACY_DOMAIN,
)

_LOGGER = getLogger(__name__)

# Shared selector for the API key field, reused by every schema (initial setup,
# reauth) so both stay visually/behaviorally in sync.
_API_KEY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _base_schema(truenas_config: Mapping[str, Any]) -> vol.Schema:
    """Generate base schema."""
    base_schema = {
        vol.Required(
            CONF_HOST, default=truenas_config.get(CONF_HOST, DEFAULT_HOST)
        ): str,
        vol.Required(
            CONF_API_KEY, default=truenas_config.get(CONF_API_KEY, "")
        ): _API_KEY_SELECTOR,
        vol.Required(
            CONF_VERIFY_SSL,
            default=truenas_config.get(CONF_VERIFY_SSL, DEFAULT_SSL_VERIFY),
        ): bool,
        vol.Required(
            CONF_CRONJOB_SKIP_DISABLED,
            default=truenas_config.get(
                CONF_CRONJOB_SKIP_DISABLED, DEFAULT_CRONJOB_SKIP_DISABLED
            ),
        ): bool,
        vol.Required(
            CONF_DATA_UNIT,
            default=truenas_config.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT),
        ): vol.In(ALLOWED_DATA_UNITS),
    }

    return vol.Schema(base_schema)


# ---------------------------
#   _map_error_to_ha
# ---------------------------
def _map_error_to_ha(errorcode: str) -> str:
    """Map TrueNAS connection error codes to Home Assistant config flow errors."""
    valid_errors = {
        ERR_CERT_VERIFY_FAILED,
        ERR_HTTP_USED,
        ERR_TLS_NOT_SUPPORTED,
        ERR_WS_NOT_SUPPORTED,
        ERR_INVALID_KEY,
        ERR_PROXY_INTERCEPTED,
        ERR_INVALID_HOSTNAME,
        ERR_UNKNOWN_HOSTNAME,
        ERR_CONNECTION_REFUSED,
        ERR_HANDSHAKE_TIMEOUT,
        ERR_API_NOT_FOUND,
        ERR_MALFORMED_RESULT,
    }
    return errorcode if errorcode in valid_errors else "unknown"


# ---------------------------
#   configured_instances
# ---------------------------
@callback
def configured_instances(hass: HomeAssistant) -> set[str]:
    """Return a set of configured instances."""
    return {
        entry.data.get(CONF_NAME, DEFAULT_DEVICE_NAME)
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


# ---------------------------
#   _sanitize_host
# ---------------------------
# Strip a leading URL scheme (e.g. "https://" or "http://") from the host.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
# Everything from the first path/query/fragment delimiter is not part of host.
_HOST_TAIL_RE = re.compile(r"[/?#]")


def _sanitize_host(host: str) -> str:
    """Normalize user input to the bare hostname/IP[:port] the API expects.

    Users frequently paste a full URL (for example
    ``https://nas.example.com/ui?tab=1``). The API layer requires a bare host,
    so strip any scheme as well as a trailing path, query or fragment here
    instead of erroring out, so the value just works.
    """
    host = host.strip()
    host = _SCHEME_RE.sub("", host)  # drop a leading scheme
    host = _HOST_TAIL_RE.split(host, maxsplit=1)[0]  # drop path/query/fragment
    return host.strip()


# ---------------------------
#   _guess_ip
# ---------------------------
def _guess_ip() -> str:
    """Try to guess the TrueNAS IP from common local hostnames."""
    for domain in ("", *KNOWN_DOMAINS):
        test_host = f"truenas.{domain}" if domain else "truenas"
        with contextlib.suppress(OSError):
            return socket.gethostbyname(test_host)
    return DEFAULT_HOST


# ---------------------------
#   _async_try_connect
# ---------------------------
async def _async_try_connect(api: TrueNASAPI, host: str, context: str) -> bool:
    """Attempt ``api.connect()``, returning False (and logging) on any failure.

    Shared by the zeroconf probe and the rediscovery match: both need to try
    one candidate connection and move on to the next on any problem rather
    than raising, so an unexpected exception here must not abort the whole
    discovery/rediscovery flow. ``quiet=True`` keeps ``connect()``'s own
    failure logging at debug too, since most probed candidates are expected
    to not be TrueNAS at all.
    """
    try:
        return await api.connect(quiet=True)
    except Exception as err:  # noqa: BLE001 - must not abort discovery on an unexpected error
        _LOGGER.debug("TrueNAS %s: %s: %s", host, context, err)
        return False


# ---------------------------
#   _async_safe_disconnect
# ---------------------------
async def _async_safe_disconnect(api: TrueNASAPI) -> None:
    """Disconnect ``api``, swallowing any error.

    Mirrors :func:`_async_try_connect`/:func:`_async_get_system_id`: cleanup
    in a probe/rediscovery ``finally`` block must never raise, or it would
    abort the whole discovery flow for every remaining candidate.
    """
    with contextlib.suppress(Exception):
        await api.disconnect()


# Ports the ``ws``/``wss`` schemes already default to; an mDNS announcement
# naming one of them adds nothing over probing the bare host.
_DEFAULT_WS_PORTS = frozenset({80, 443})


# ---------------------------
#   _probe_candidates
# ---------------------------
def _probe_candidates(host: str, port: int | None) -> list[str]:
    """Return the host strings to probe for ``host``, most likely first.

    TrueNAS only advertises the generic ``_http._tcp`` service, whose port is
    the web UI's -- normally 80, which ``ws`` already defaults to (as ``wss``
    does 443). Probing the bare host therefore stays first so a standard box
    reachable over ``wss`` is not forced onto the advertised plain-HTTP port.
    A genuinely non-default port is appended as a fallback, so an instance
    behind a custom port or reverse proxy is no longer misread as "not
    TrueNAS". ``aiotruenas`` builds its URL from the host verbatim, so
    ``host:port`` is a valid host string here (see ``_sanitize_host``).
    """
    if port is None or port in _DEFAULT_WS_PORTS:
        return [host]
    return [host, f"{host}:{port}"]


# ---------------------------
#   _async_probe_candidate
# ---------------------------
async def _async_probe_candidate(host: str) -> bool:
    """Return True only if ``host`` rejects a bogus API key as invalid.

    Only a genuine TrueNAS JSON-RPC endpoint completes the WebSocket
    handshake and then answers ``ERR_INVALID_KEY``; every other outcome is
    treated as "not TrueNAS".
    """
    for scheme in ("wss", "ws"):
        api = TrueNASAPI(host, "-", verify_ssl=False, scheme=scheme)
        try:
            # A rejected bogus key surfaces as connect() returning False with
            # api.error == ERR_INVALID_KEY, not as a truthy connect() result --
            # so api.error must be checked regardless of the connect outcome,
            # or every genuine TrueNAS probe is misread as "not reachable".
            await _async_try_connect(api, host, f"probe ({scheme}) is not reachable")
            if api.error == ERR_INVALID_KEY:
                return True
        finally:
            await _async_safe_disconnect(api)
    return False


# ---------------------------
#   _async_get_system_id
# ---------------------------
async def _async_get_system_id(api: TrueNASAPI, host: str) -> str | None:
    """Fetch ``system.global.id``, returning None (and logging) on failure.

    A failed identity lookup must never block configuration/rediscovery, so
    any exception here is swallowed and treated the same as "no id yet".
    """
    try:
        system_id = await api.query("system.global.id")
    except Exception as err:  # noqa: BLE001 - a failed lookup must never block config/rediscovery
        _LOGGER.debug("TrueNAS %s: failed to read system.global.id: %s", host, err)
        return None

    if isinstance(system_id, str) and system_id:
        return system_id

    if not isinstance(system_id, str):
        _LOGGER.debug(
            "TrueNAS %s: unexpected system.global.id payload (%s): %r",
            host,
            type(system_id).__name__,
            system_id,
        )

    return None


# ---------------------------
#   _async_get_hostname
# ---------------------------
async def _async_get_hostname(api: TrueNASAPI, host: str) -> str:
    """Fetch ``system.info.hostname``, falling back to DEFAULT_DEVICE_NAME.

    Used to auto-generate the config entry's name/title from the device
    itself instead of asking the user to type one; a failed lookup must
    never block setup, so any problem here is swallowed and treated the
    same as "use the generic default".
    """
    try:
        info = await api.query("system.info")
    except Exception as err:  # noqa: BLE001 - a failed lookup must never block setup
        _LOGGER.debug("TrueNAS %s: failed to read system.info: %s", host, err)
        return DEFAULT_DEVICE_NAME

    if isinstance(info, dict):
        hostname = info.get("hostname")
        if isinstance(hostname, str) and hostname:
            return hostname

    return DEFAULT_DEVICE_NAME


# ---------------------------
#   TrueNASConfigFlow
# ---------------------------
class TrueNASConfigFlow(ConfigFlow, domain=DOMAIN):
    """TrueNASConfigFlow class."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.truenas_config: dict[str, Any] = {}
        # Options of a taken-over legacy entry, applied when the entry is created.
        self._legacy_options: dict[str, Any] = {}
        # Guard so the legacy-takeover offer is made at most once per flow.
        self._migration_checked = False

    async def _validate_connection(
        self, config: dict[str, Any], errors: dict[str, str]
    ) -> None:
        """Test the API connection and record a mapped error on failure."""
        try:
            api = TrueNASAPI(
                config[CONF_HOST],
                config[CONF_API_KEY],
                config[CONF_VERIFY_SSL],
            )
        except ValueError:
            # _sanitize_host already removes a scheme/path up front, so this
            # only triggers for a genuinely malformed host that the API layer
            # still rejects. Surface a clear error instead of an unhandled
            # exception (which the frontend reports as a generic failure).
            errors[CONF_HOST] = ERR_INVALID_HOSTNAME
            _LOGGER.error(
                "TrueNAS host %r is not a usable hostname or IP address",
                config.get(CONF_HOST),
            )
            return

        conn, errorcode = await api.connection_test()
        if conn:
            system_id = await _async_get_system_id(api, config.get(CONF_HOST, ""))
            if system_id:
                config[CONF_SYSTEM_ID] = system_id
            # Only auto-derive the name on a genuinely new entry. A legacy
            # migration or an existing entry (reauth) pre-seeds this from data
            # the user never re-enters, and legacy migration in particular
            # requires keeping the exact original value so unique_ids still
            # match (see async_step_migrate_import).
            if not config.get(CONF_NAME):
                config[CONF_NAME] = await _async_get_hostname(
                    api, config.get(CONF_HOST, "")
                )
        await api.disconnect()

        if not conn:
            ha_error = _map_error_to_ha(errorcode)
            errors[CONF_HOST] = ha_error
            _LOGGER.error(
                "TrueNAS connection error (%s) mapped to HA error '%s'",
                errorcode,
                ha_error,
            )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # Offer to take over an existing legacy ``truenas`` configuration once,
        # before the (possibly prefilled) form is shown. Inert in the legacy
        # integration itself (see _find_legacy_config).
        if user_input is None and not self._migration_checked:
            self._migration_checked = True
            if self._find_legacy_config() is not None:
                return await self.async_step_migrate()

        truenas_config = self.truenas_config
        errors: dict[str, str] = {}

        if user_input is None and not truenas_config.get(CONF_HOST):
            default_host = await self.hass.async_add_executor_job(_guess_ip)
            _LOGGER.debug("Auto-discovered default host: %s", default_host)
            truenas_config[CONF_HOST] = default_host

        if user_input is not None:
            result = await self._async_apply_user_input(
                user_input, truenas_config, errors
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(truenas_config),
            errors=errors,
        )

    async def _async_apply_user_input(
        self,
        user_input: dict[str, Any],
        truenas_config: dict[str, Any],
        errors: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate a submitted user form.

        Returns the created entry on success, or ``None`` to re-show the form
        with ``errors`` populated. Split out of ``async_step_user`` to keep its
        cognitive complexity within bounds (SonarQube S3776).
        """
        if CONF_HOST in user_input:
            user_input[CONF_HOST] = _sanitize_host(user_input[CONF_HOST])
        truenas_config |= user_input

        # The same device must not be configurable twice: abort when another
        # entry already points at this host (the name check below alone would
        # let the same host in again under a different name).
        self._async_abort_entries_match({CONF_HOST: truenas_config[CONF_HOST]})

        # The name is derived from the device itself (see _validate_connection),
        # not chosen by the user, so it is only known -- and only worth
        # checking for a collision -- once a connection attempt succeeds.
        await self._validate_connection(truenas_config, errors)

        if not errors and truenas_config[CONF_NAME] in configured_instances(self.hass):
            errors["base"] = "name_exists"

        # Once the box's stable identity is known, key the entry's unique_id
        # on it rather than on the (zeroconf-set) host, so rediscovery and
        # de-duplication survive the host/IP changing later.
        system_id = truenas_config.get(CONF_SYSTEM_ID)
        if not errors and isinstance(system_id, str) and system_id:
            await self.async_set_unique_id(system_id)
            self._abort_if_unique_id_configured()

        # Save instance
        if not errors:
            return self.async_create_entry(
                title=truenas_config[CONF_NAME],
                data=truenas_config,
                options=self._legacy_options or None,
            )
        return None

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a TrueNAS instance discovered over mDNS.

        TrueNAS SCALE only advertises the generic ``_http._tcp`` service
        type shared by countless unrelated devices (printers, routers,
        media servers, ...), so the zeroconf type match alone cannot tell
        TrueNAS apart. Instead, probe the discovered host with a bogus API
        key: only a genuine TrueNAS JSON-RPC endpoint answers the WebSocket
        handshake and then rejects it specifically as an invalid key
        (``ERR_INVALID_KEY``). Any other outcome (connection refused,
        handshake timeout, ...) means some other device is behind that
        _http._tcp announcement, so the flow aborts silently without ever
        showing the user anything.
        """
        host = discovery_info.host
        self._async_abort_entries_match({CONF_HOST: host})
        # Provisional only, to dedupe concurrent zeroconf events for this host
        # before the box's stable system_id is known; the shared finish step
        # (see async_step_user's system_id handling) re-keys the unique_id to
        # that stable id once the probe below succeeds.
        await self.async_set_unique_id(  # pylint: disable=home-assistant-unique-id-ip-based
            host
        )
        self._abort_if_unique_id_configured()

        # The probe reports back which endpoint actually answered, so a box
        # found only on its advertised non-default port is configured with
        # that port instead of silently falling back to the default one.
        probed_host = await self._probe_is_truenas(host, discovery_info.port)
        if probed_host is None:
            return self.async_abort(reason="not_truenas")

        if await self._async_update_rediscovered_entry(probed_host):
            return self.async_abort(reason="already_configured")

        self.truenas_config[CONF_HOST] = probed_host
        self.context["title_placeholders"] = {CONF_NAME: probed_host}
        return await self.async_step_zeroconf_confirm()

    @staticmethod
    async def _probe_is_truenas(host: str, port: int | None = None) -> str | None:
        """Return the ``host[:port]`` that answers as TrueNAS, or None.

        Any unexpected connection-level error (refused, DNS, handshake, ...)
        is treated the same as "not TrueNAS" so a misbehaving non-TrueNAS
        device cannot abort zeroconf discovery for the whole flow.

        The returned value is what the entry must be configured with, so a
        box found only on its advertised non-default port keeps that port.
        """
        for candidate in _probe_candidates(host, port):
            if await _async_probe_candidate(candidate):
                return candidate
        return None

    async def _async_update_rediscovered_entry(self, host: str) -> bool:
        """Update an existing entry's host if ``host`` is the same box, moved.

        Tries each configured entry's own stored API key against the newly
        discovered (and already-confirmed-TrueNAS) host. A successful login
        whose ``system.global.id`` matches the entry's stored id is proof
        it's the same physical box under a new IP. A successful login with
        no stored id yet (entries predating this check) is only accepted as
        best-effort confirmation when this is the sole configured entry, so
        there's no other entry it could be confused with; with more than one
        entry configured, an id-less match is skipped rather than risk
        migrating the wrong entry. Returns True (and updates+reloads the
        entry) on a match, False otherwise.
        """
        entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if entry.data.get(CONF_HOST) == host:
                continue

            api = TrueNASAPI(
                host,
                entry.data.get(CONF_API_KEY, ""),
                entry.data.get(CONF_VERIFY_SSL, DEFAULT_SSL_VERIFY),
            )
            try:
                # A connection-level failure (DNS, refused, SSL, ...) must not
                # abort rediscovery for the other entries; treat it the same
                # as "not a match" and move on, like _probe_is_truenas does.
                if not await _async_try_connect(
                    api,
                    host,
                    "failed to connect while checking for a rediscovery match",
                ):
                    continue
                # A failed identity lookup must not abort rediscovery either;
                # fall back to the same best-effort match used for entries
                # that predate this check (see docstring).
                system_id = await _async_get_system_id(api, host)
            finally:
                await _async_safe_disconnect(api)

            stored_id = entry.data.get(CONF_SYSTEM_ID)
            if stored_id and system_id != stored_id:
                continue  # same key, different box -- not a match
            if not stored_id and len(entries) > 1:
                continue  # no id to confirm identity, and ambiguous

            new_data = dict(entry.data)
            new_data[CONF_HOST] = host
            update_kwargs: dict[str, Any] = {"data": new_data}
            if isinstance(system_id, str) and system_id:
                new_data[CONF_SYSTEM_ID] = system_id
                # Migrate the entry's unique_id onto the stable box identity
                # too, so future rediscovery keys on it rather than the host.
                update_kwargs["unique_id"] = system_id
            self.hass.config_entries.async_update_entry(entry, **update_kwargs)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return True
        return False

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm setup of the discovered TrueNAS host."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={CONF_HOST: self.truenas_config[CONF_HOST]},
        )

    def _find_legacy_config(self) -> ConfigEntry | None:
        """Return a legacy ``truenas`` entry to optionally take over, if any.

        Only relevant in the renamed (``truenas_ce``) integration; inert while
        ``DOMAIN == LEGACY_DOMAIN`` so the takeover never appears pre-rename.
        """
        if DOMAIN == LEGACY_DOMAIN:
            return None
        legacy_entries = self.hass.config_entries.async_entries(LEGACY_DOMAIN)
        return legacy_entries[0] if legacy_entries else None

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to import an existing TrueNAS configuration or start fresh."""
        return self.async_show_menu(
            step_id="migrate",
            menu_options=["migrate_import", "migrate_manual"],
        )

    async def async_step_migrate_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prefill the form from the detected legacy entry, then show it.

        Importing the same name is required: the entity unique_ids derive from
        it, so the migration in __init__.py can re-attach the old entity_ids.
        """
        legacy = self._find_legacy_config()
        if legacy is not None:
            self.truenas_config.update(
                {
                    CONF_NAME: legacy.data.get(CONF_NAME, DEFAULT_DEVICE_NAME),
                    CONF_HOST: legacy.data.get(CONF_HOST, DEFAULT_HOST),
                    CONF_API_KEY: legacy.data.get(CONF_API_KEY, ""),
                    CONF_VERIFY_SSL: legacy.data.get(
                        CONF_VERIFY_SSL, DEFAULT_SSL_VERIFY
                    ),
                    CONF_CRONJOB_SKIP_DISABLED: legacy.data.get(
                        CONF_CRONJOB_SKIP_DISABLED, DEFAULT_CRONJOB_SKIP_DISABLED
                    ),
                    CONF_DATA_UNIT: legacy.data.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT),
                }
            )
            self._legacy_options = dict(legacy.options)
        return await self.async_step_user()

    async def async_step_migrate_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Skip the takeover and configure TrueNAS CE from scratch."""
        return await self.async_step_user()
