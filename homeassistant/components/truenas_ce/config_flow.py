"""Config flow to configure TrueNAS."""

from collections.abc import Mapping
import contextlib
from logging import getLogger
import socket
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import TrueNASAPI
from .const import (
    ALLOWED_DATA_UNITS,
    CONF_DATA_UNIT,
    CONF_SYSTEM_ID,
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
)
from .helper import sanitize_host

_LOGGER = getLogger(__name__)

_API_KEY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _base_schema(truenas_config: Mapping[str, Any]) -> vol.Schema:
    """Generate base schema.

    The API key default is never pre-filled, unlike every other field:
    a secret would otherwise be embedded in the frontend's form state.
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
            CONF_DATA_UNIT,
            default=truenas_config.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT),
        ): vol.In(ALLOWED_DATA_UNITS),
    }

    return vol.Schema(base_schema)


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


def _guess_ip() -> str:
    """Try to guess the TrueNAS IP from common local hostnames."""
    for domain in ("", *KNOWN_DOMAINS):
        test_host = f"truenas.{domain}" if domain else "truenas"
        with contextlib.suppress(OSError):
            return socket.gethostbyname(test_host)
    return DEFAULT_HOST


async def _async_try_connect(api: TrueNASAPI, host: str, context: str) -> bool:
    """Attempt ``api.connect()``, returning False (and logging) on any failure.

    Used by the zeroconf probe so one bad candidate can't abort discovery.
    """
    try:
        return await api.connect(quiet=True)
    except Exception as err:  # noqa: BLE001 - must not abort discovery on an unexpected error
        _LOGGER.debug("TrueNAS %s: %s: %s", host, context, err)
        return False


async def _async_safe_disconnect(api: TrueNASAPI) -> None:
    """Disconnect ``api``, swallowing any error.

    Cleanup in a probe/rediscovery ``finally`` block must never raise.
    """
    with contextlib.suppress(Exception):
        await api.disconnect()


# ws/wss already default to 80/443; an mDNS-advertised port matching one of
# those adds nothing over probing the bare host.
_DEFAULT_WS_PORTS = frozenset({80, 443})


def _probe_candidates(host: str, port: int | None) -> list[str]:
    """Return the host strings to probe for ``host``, most likely first.

    The bare host is tried first so a standard box on ``wss`` isn't forced
    onto the advertised plain-HTTP port; a genuinely non-default port is
    appended as a fallback for custom ports/reverse proxies.
    """
    if port is None or port in _DEFAULT_WS_PORTS:
        return [host]
    return [host, f"{host}:{port}"]


async def _async_probe_candidate(host: str) -> bool:
    """Return True only if ``host`` rejects a bogus API key as invalid.

    Only a genuine TrueNAS JSON-RPC endpoint answers ``ERR_INVALID_KEY``.
    """
    for scheme in ("wss", "ws"):
        api = TrueNASAPI(host, "-", verify_ssl=False, scheme=scheme)
        try:
            # connect() returns False either way, so api.error (not the
            # return value) is what distinguishes a rejected key from "unreachable".
            await _async_try_connect(api, host, f"probe ({scheme}) is not reachable")
            if api.error == ERR_INVALID_KEY:
                return True
        finally:
            await _async_safe_disconnect(api)
    return False


async def _async_get_system_id(api: TrueNASAPI, host: str) -> str | None:
    """Fetch ``system.global.id``, returning None (and logging) on failure.

    A failed lookup must never block configuration/rediscovery.
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


async def _async_get_hostname(api: TrueNASAPI, host: str) -> str:
    """Fetch ``system.info.hostname``, falling back to DEFAULT_DEVICE_NAME.

    Auto-generates the entry's name/title; a failed lookup must not block setup.
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


class TrueNASConfigFlow(ConfigFlow, domain=DOMAIN):
    """TrueNASConfigFlow class."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.truenas_config: dict[str, Any] = {}

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
            # Only triggers for a malformed host sanitize_host didn't catch.
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
        with ``errors`` populated. Split out to keep cognitive complexity
        within bounds (SonarQube S3776).
        """
        if CONF_HOST in user_input:
            user_input[CONF_HOST] = sanitize_host(user_input[CONF_HOST])
        # A blank resubmit keeps the previously known key (see _base_schema).
        if user_input.get(CONF_API_KEY, "") == "" and truenas_config.get(CONF_API_KEY):
            user_input.pop(CONF_API_KEY, None)
        truenas_config |= user_input

        self._async_abort_entries_match({CONF_HOST: truenas_config[CONF_HOST]})

        await self._validate_connection(truenas_config, errors)

        # Key unique_id on the stable system_id (not the host) so rediscovery
        # survives IP changes; safe to fold the host into a matched entry
        # here because this flow authenticated it itself.
        system_id = truenas_config.get(CONF_SYSTEM_ID)
        if not errors and isinstance(system_id, str) and system_id:
            await self.async_set_unique_id(system_id)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: truenas_config[CONF_HOST],
                    CONF_API_KEY: truenas_config[CONF_API_KEY],
                    CONF_VERIFY_SSL: truenas_config[CONF_VERIFY_SSL],
                }
            )

        if not errors:
            return self.async_create_entry(
                title=truenas_config[CONF_NAME],
                data=truenas_config,
            )
        return None

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a TrueNAS instance discovered over mDNS.

        The generic ``_http._tcp`` service type matches many unrelated
        devices, so the host is probed with a bogus API key first; only a
        genuine TrueNAS endpoint answers ``ERR_INVALID_KEY``. A confirmed
        host is never used to silently replay a stored key from an existing
        entry (a spoofed device could mimic the probe) -- the flow always
        falls through to the user-facing confirm step instead.
        """
        host = sanitize_host(discovery_info.host)
        self._async_abort_entries_match({CONF_HOST: host})
        # Provisional unique_id to dedupe concurrent events; re-keyed to the
        # stable system_id once the probe below succeeds.
        await self.async_set_unique_id(  # pylint: disable=home-assistant-unique-id-ip-based
            host
        )
        self._abort_if_unique_id_configured()

        probed_host = await self._probe_is_truenas(host, discovery_info.port)
        if probed_host is None:
            return self.async_abort(reason="not_truenas")

        self.truenas_config[CONF_HOST] = probed_host
        self.context["title_placeholders"] = {CONF_NAME: probed_host}
        return await self.async_step_zeroconf_confirm()

    @staticmethod
    async def _probe_is_truenas(host: str, port: int | None = None) -> str | None:
        """Return the ``host[:port]`` that answers as TrueNAS, or None.

        Any connection-level error is treated the same as "not TrueNAS".
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
