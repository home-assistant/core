"""Config flow to configure TrueNAS."""

from collections.abc import Mapping
import contextlib
from logging import getLogger
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
    MIGRATION_DONE,
)
from .helper import sanitize_host

_LOGGER = getLogger(__name__)

# Shared selector for the API key field, reused by every schema.
_API_KEY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _base_schema(truenas_config: Mapping[str, Any]) -> vol.Schema:
    """Generate base schema.

    The API key default is intentionally never pre-filled from
    ``truenas_config`` (e.g. a taken-over legacy entry), even though every
    other field is: a secret's value would otherwise be embedded in the
    frontend's form state and re-submitted in cleartext. Leaving it blank is
    safe because ``_async_apply_user_input`` keeps the previously known key
    when the field comes back empty.
    """
    base_schema = {
        vol.Required(
            CONF_HOST, default=truenas_config.get(CONF_HOST, DEFAULT_HOST)
        ): str,
        vol.Required(CONF_API_KEY, default=""): _API_KEY_SELECTOR,
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

    Used by the zeroconf probe, which needs to try one candidate connection
    and move on to the next on any problem rather than raising, so an
    unexpected exception here must not abort the whole discovery flow.
    ``quiet=True`` keeps ``connect()``'s own failure logging at debug too,
    since most probed candidates are expected to not be TrueNAS at all.
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
    ``host:port`` is a valid host string here (see ``sanitize_host``).
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
            # sanitize_host already removes a scheme/path up front, so this
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
        await _async_safe_disconnect(api)

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
            user_input[CONF_HOST] = sanitize_host(user_input[CONF_HOST])
        # An empty submission keeps a previously known key (from a taken-over
        # legacy entry) rather than blanking it out -- the field is never
        # pre-filled (see _base_schema), so a blank resubmit means "unchanged".
        if user_input.get(CONF_API_KEY, "") == "" and truenas_config.get(CONF_API_KEY):
            user_input.pop(CONF_API_KEY, None)
        truenas_config |= user_input

        # The same device must not be configurable twice: abort when another
        # entry already points at this host.
        self._async_abort_entries_match({CONF_HOST: truenas_config[CONF_HOST]})

        await self._validate_connection(truenas_config, errors)

        # Once the box's stable identity is known, key the entry's unique_id
        # on it rather than on the (zeroconf-set) host, so rediscovery and
        # de-duplication survive the host/IP changing later. A match here is
        # only ever reached after *this* flow has itself authenticated to the
        # host with a real (user-typed or taken-over) API key -- never with
        # another entry's stored credential -- so it is safe to fold the new
        # host into the matched entry via ``updates`` instead of just
        # aborting: the box's identity was confirmed through this flow's own
        # authenticated connection, not by trusting the discovery source.
        system_id = truenas_config.get(CONF_SYSTEM_ID)
        if not errors and isinstance(system_id, str) and system_id:
            await self.async_set_unique_id(system_id)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: truenas_config[CONF_HOST]}
            )

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

        A confirmed-TrueNAS-like host is deliberately never used to silently
        replay a stored API key from an existing entry: that endpoint is only
        known to answer the tiny probe handshake, which a spoofed device on
        the same network can mimic, so treating it as proof of identity would
        leak real credentials to whatever actually answered the discovery
        broadcast. The flow always falls through to the user-facing confirm
        step instead; only a connection this flow itself authenticates (see
        ``_async_apply_user_input``) can establish the box's real identity
        and fold a rediscovered host into an existing entry.
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
        With more than one legacy entry (multiple boxes set up under the old
        integration), a host already known at this point (e.g. from zeroconf
        discovery) picks the matching one instead of always offering the
        first; with no host known yet and more than one legacy entry, none is
        offered here (ambiguous -- the user can still migrate manually).
        """
        if DOMAIN == LEGACY_DOMAIN:
            return None
        legacy_entries = self.hass.config_entries.async_entries(LEGACY_DOMAIN)
        if not legacy_entries:
            return None
        if host := self.truenas_config.get(CONF_HOST):
            sanitized_host = sanitize_host(host)
            for entry in legacy_entries:
                entry_host = entry.data.get(CONF_HOST)
                if entry_host and sanitize_host(entry_host) == sanitized_host:
                    return entry
        return legacy_entries[0] if len(legacy_entries) == 1 else None

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
        """Skip the takeover and configure TrueNAS CE from scratch.

        Marks the entry as already migrated so ``async_adopt_legacy_entities``
        never auto-adopts the legacy entry later -- without this, entering the
        same host the legacy entry uses would silently override the user's
        explicit "from scratch" choice on the first coordinator setup.
        """
        self.truenas_config[MIGRATION_DONE] = True
        return await self.async_step_user()
