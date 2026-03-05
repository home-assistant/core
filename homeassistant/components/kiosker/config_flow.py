"""Config flow for the Kiosker integration."""

from __future__ import annotations

import logging
from typing import Any

from kiosker import (
    AuthenticationError,
    BadRequestError,
    ConnectionError,
    IPAuthenticationError,
    KioskerAPI,
    PingError,
    TLSVerificationError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_API_TOKEN, DEFAULT_SSL, DEFAULT_SSL_VERIFY, DOMAIN, PORT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_SSL_VERIFY): bool,
    }
)
STEP_ZEROCONF_CONFIRM_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_SSL_VERIFY): bool,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, str], str | None]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    Returns a tuple of (errors dict, device_id). If validation succeeds, errors will be empty.
    """
    api = KioskerAPI(
        host=data[CONF_HOST],
        port=PORT,
        token=data[CONF_API_TOKEN],
        ssl=data[CONF_SSL],
        verify=data[CONF_VERIFY_SSL],
    )

    try:
        # Test connection by getting status
        status = await hass.async_add_executor_job(api.status)
    except ConnectionError:
        return ({"base": "cannot_connect"}, None)
    except AuthenticationError:
        return ({"base": "invalid_auth"}, None)
    except IPAuthenticationError:
        return ({"base": "invalid_ip_auth"}, None)
    except TLSVerificationError:
        return ({"base": "tls_error"}, None)
    except BadRequestError:
        return ({"base": "bad_request"}, None)
    except PingError:
        return ({"base": "cannot_connect"}, None)
    except Exception:
        _LOGGER.exception("Unexpected exception while connecting to Kiosker")
        return ({"base": "unknown"}, None)

    # Ensure we have a device_id from the status response
    if not status.device_id:
        _LOGGER.error("Device did not return a valid device_id")
        return ({"base": "cannot_connect"}, None)

    return ({}, status.device_id)


class KioskerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kiosker."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""

        self._discovered_host: str | None = None
        self._discovered_device_id: str | None = None
        self._discovered_version: str | None = None
        self._discovered_ssl: bool | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            validation_errors, device_id = await validate_input(self.hass, user_input)
            if validation_errors:
                errors.update(validation_errors)
            elif device_id:
                # Use device ID as unique identifier
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                # Use first 8 characters of device_id for consistency with entity naming
                display_id = device_id[:8] if len(device_id) > 8 else device_id
                title = f"Kiosker {display_id}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host

        # Extract device information from zeroconf properties
        properties = discovery_info.properties
        device_id = properties.get("uuid")
        app_name = properties.get("app", "Kiosker")
        version = properties.get("version", "")
        ssl = properties.get("ssl", "false").lower() == "true"

        # Use device_id from zeroconf
        if device_id:
            device_name = f"{app_name} ({device_id[:8].upper()})"
            unique_id = device_id
        else:
            _LOGGER.debug("Zeroconf properties did not include a valid device_id")
            return self.async_abort(reason="cannot_connect")

        # Set unique ID and check for duplicates
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Store discovery info for confirmation step
        self.context["title_placeholders"] = {
            "name": device_name,
            "host": host,
            "ssl": ssl,
        }

        # Store discovered information for later use
        self._discovered_host = host
        self._discovered_device_id = device_id
        self._discovered_version = version
        self._discovered_ssl = ssl

        # Show confirmation dialog
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle zeroconf confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Use stored discovery info and user-provided token
            host = self._discovered_host
            ssl = self._discovered_ssl

            # Create config with discovered host and user-provided token
            config_data = {
                CONF_HOST: host,
                CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                CONF_SSL: ssl,
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, DEFAULT_SSL_VERIFY),
            }

            validation_errors, device_id = await validate_input(self.hass, config_data)
            if validation_errors:
                errors.update(validation_errors)
            elif device_id:
                # Use first 8 characters of device_id for consistency with entity naming
                display_id = device_id[:8] if len(device_id) > 8 else device_id
                title = f"Kiosker {display_id}"
                return self.async_create_entry(title=title, data=config_data)

        # Show form to get API token for discovered device
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=STEP_ZEROCONF_CONFIRM_DATA_SCHEMA,
            description_placeholders=self.context["title_placeholders"],
            errors=errors,
        )
