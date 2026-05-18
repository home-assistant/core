"""Config/options flow form schemas and Fritz!Box connection validation."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from fritzboxvpn import FritzBoxVPNSession
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_UPDATE_INTERVAL,
    ERROR_INDICATOR_AUTH,
    ERROR_INDICATOR_CONNECT,
    ERROR_KEY_CANNOT_CONNECT,
    ERROR_KEY_INVALID_AUTH,
    ERROR_KEY_INVALID_HOST,
    ERROR_KEY_UNKNOWN,
    INTEGRATION_TITLE,
    UPDATE_INTERVAL_MAX,
    UPDATE_INTERVAL_MIN,
    password_from_sources,
)
from .coordinator import normalize_update_interval

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


def validate_host(host: str) -> str:
    """Validate host is a valid IP address or hostname."""
    if not host or not isinstance(host, str):
        raise vol.Invalid("Host must be a non-empty string")

    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass

    if len(host) > 253:
        raise vol.Invalid("Hostname too long (max 253 characters)")

    if not all(c.isalnum() or c in (".", "-") for c in host):
        raise vol.Invalid("Invalid hostname format")

    if host.startswith(".") or host.endswith(".") or host.startswith("-") or host.endswith("-"):
        raise vol.Invalid("Hostname cannot start or end with dot or hyphen")

    return host


def credentials_defaults(
    config: Mapping[str, Any] | None,
    host_fallback: str = DEFAULT_HOST,
    extra_password_sources: tuple[Mapping[str, Any] | None, ...] = (),
) -> tuple[str, str, str]:
    """Host, username, and password defaults for credential forms."""
    if not config:
        return (host_fallback, "", "")
    host = config.get(CONF_HOST) or host_fallback
    username = config.get(CONF_USERNAME) or ""
    password = password_from_sources(config, *extra_password_sources)
    return (host, username, password)


def fill_password_if_missing(
    user_input: dict[str, Any], *sources: Mapping[str, Any] | None
) -> None:
    """Set user_input password from first non-empty source if missing."""
    if user_input.get(CONF_PASSWORD):
        return
    user_input[CONF_PASSWORD] = password_from_sources(*sources)


def validate_host_on_submit(user_input: dict[str, Any], errors: dict[str, str]) -> bool:
    """Validate host from submitted user_input and set form field error."""
    try:
        validate_host(str(user_input.get(CONF_HOST, "")))
    except vol.Invalid:
        errors[CONF_HOST] = ERROR_KEY_INVALID_HOST
        return False
    return True


def credentials_schema(
    host_default: str, username_default: str, password_default: str
) -> vol.Schema:
    """Credentials form (host, username, password) with given defaults."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host_default): str,
            vol.Required(CONF_USERNAME, default=username_default): str,
            vol.Required(CONF_PASSWORD, default=password_default): str,
        }
    )


def configure_schema(
    current_data: dict[str, Any], current_options: dict[str, Any]
) -> vol.Schema:
    """Configure step schema with defaults from current config/options."""
    host_default, username_default, _ = credentials_defaults(current_data)
    try:
        host_default = validate_host(host_default)
    except vol.Invalid:
        _LOGGER.warning(
            "Invalid host in config entry for options form. Falling back to default host.",
        )
        host_default = DEFAULT_HOST
    default_update_interval = normalize_update_interval(
        current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host_default): str,
            vol.Required(CONF_USERNAME, default=username_default): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Required(CONF_UPDATE_INTERVAL, default=default_update_interval): vol.All(
                vol.Coerce(int),
                vol.Range(min=UPDATE_INTERVAL_MIN, max=UPDATE_INTERVAL_MAX),
            ),
        }
    )


def confirm_schema(
    existing_config: Mapping[str, Any] | None,
    discovered_host: str | None,
    current_input: Mapping[str, Any] | None = None,
) -> vol.Schema:
    """Schema for SSDP confirm step from existing config or current form input."""
    host_fallback = discovered_host or DEFAULT_HOST
    source = current_input if current_input is not None else existing_config
    extra_password_sources = (existing_config,) if current_input is not None else ()
    return credentials_schema(
        *credentials_defaults(source, host_fallback, extra_password_sources)
    )


def reauth_schema(username_default: str) -> vol.Schema:
    """Schema for reauthentication (username + password only)."""
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username_default): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


def confirm_checkbox_schema() -> vol.Schema:
    """Single confirm checkbox for destructive options steps."""
    return vol.Schema({vol.Required("confirm", default=False): bool})


def validation_error_key(error_msg: str) -> str:
    """Map validation exception message to config flow error key."""
    msg_lower = error_msg.lower()
    if any(ind in msg_lower for ind in ERROR_INDICATOR_AUTH):
        return ERROR_KEY_INVALID_AUTH
    if any(ind in msg_lower for ind in ERROR_INDICATOR_CONNECT):
        return ERROR_KEY_CANNOT_CONNECT
    return ERROR_KEY_UNKNOWN


def set_validation_error(
    errors: dict[str, str], err: Exception, *, log_unknown_details: bool
) -> None:
    """Set config-flow error key from validation exception."""
    if isinstance(err, CannotConnect):
        errors["base"] = ERROR_KEY_CANNOT_CONNECT
        return
    if isinstance(err, InvalidAuth):
        errors["base"] = ERROR_KEY_INVALID_AUTH
        return

    error_msg = str(err)
    _LOGGER.exception(
        "Unexpected exception during validation (%s)",
        type(err).__name__,
    )
    errors["base"] = validation_error_key(error_msg)
    if log_unknown_details and errors["base"] == ERROR_KEY_UNKNOWN:
        _LOGGER.error(
            "Unknown error details during validation (%s)",
            type(err).__name__,
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate Fritz!Box connectivity; VPN connections are discovered at setup."""
    session = FritzBoxVPNSession(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_USERNAME],
        password_from_sources(data),
    )

    try:
        await session.async_get_session()
        await session.async_close()
        return {"title": f"{INTEGRATION_TITLE} ({data[CONF_HOST]})"}
    except Exception as err:
        error_msg = str(err)
        if any(ind in error_msg.lower() for ind in ERROR_INDICATOR_AUTH):
            _LOGGER.warning(
                "Authentication failed (check credentials and TR-064). Error: %s",
                error_msg,
            )
            raise InvalidAuth from err
        _LOGGER.exception("Error validating input: %s", err)
        raise CannotConnect from err
