"""Config flow to configure TrueNAS."""

from collections.abc import Mapping
import contextlib
from logging import getLogger
import socket
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.helpers import selector

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
    ERR_TIMEOUT,
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


def _base_schema(truenas_config: Mapping[str, Any]) -> probatio.Schema:
    """Generate base schema.

    The API key default is never pre-filled, unlike every other field:
    a secret would otherwise be embedded in the frontend's form state.
    """
    base_schema = {
        probatio.Required(
            CONF_HOST, default=truenas_config.get(CONF_HOST, DEFAULT_HOST)
        ): str,
        probatio.Required(CONF_API_KEY, default=""): _API_KEY_SELECTOR,
        probatio.Required(
            CONF_VERIFY_SSL,
            default=truenas_config.get(CONF_VERIFY_SSL, DEFAULT_SSL_VERIFY),
        ): bool,
        probatio.Required(
            CONF_DATA_UNIT,
            default=truenas_config.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT),
        ): probatio.In(ALLOWED_DATA_UNITS),
    }

    return probatio.Schema(base_schema)


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
        ERR_TIMEOUT,
    }
    return errorcode if errorcode in valid_errors else "unknown"


def _guess_ip() -> str:
    """Try to guess the TrueNAS IP from common local hostnames."""
    for domain in ("", *KNOWN_DOMAINS):
        test_host = f"truenas.{domain}" if domain else "truenas"
        with contextlib.suppress(OSError):
            return socket.gethostbyname(test_host)
    return DEFAULT_HOST


async def _async_safe_disconnect(api: TrueNASAPI) -> None:
    """Disconnect ``api``, swallowing any error."""
    with contextlib.suppress(Exception):
        await api.disconnect()


async def _async_get_system_id(api: TrueNASAPI, host: str) -> str | None:
    """Fetch ``system.global.id``, returning None (and logging) on failure."""
    try:
        system_id = await api.query("system.global.id")
    except Exception as err:  # noqa: BLE001
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
    """Fetch ``system.info.hostname``, falling back to DEFAULT_DEVICE_NAME."""
    try:
        info = await api.query("system.info")
    except Exception as err:  # noqa: BLE001
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

        conn = False
        errorcode = ""
        try:
            conn, errorcode = await api.connection_test()
        except Exception:
            # A bug inside aiotruenas itself must degrade to a retryable
            # "unknown" form error, not crash the flow.
            _LOGGER.exception(
                "TrueNAS %s: connection_test() raised unexpectedly",
                config.get(CONF_HOST, ""),
            )
        else:
            if conn:
                system_id = await _async_get_system_id(api, config.get(CONF_HOST, ""))
                if system_id:
                    config[CONF_SYSTEM_ID] = system_id
                if not config.get(CONF_NAME):
                    config[CONF_NAME] = await _async_get_hostname(
                        api, config.get(CONF_HOST, "")
                    )
        finally:
            # Runs on both the success and the swallowed-exception path, so
            # an already-open WebSocket is never leaked either way.
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

        # Key unique_id on the stable system_id (not the host) so an entry
        # survives an IP change; the host is folded onto the matched entry
        # because this flow just authenticated it.
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
            data_unit = truenas_config.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT)
            data = {k: v for k, v in truenas_config.items() if k != CONF_DATA_UNIT}
            return self.async_create_entry(
                title=truenas_config[CONF_NAME],
                data=data,
                options={CONF_DATA_UNIT: data_unit},
            )
        return None
