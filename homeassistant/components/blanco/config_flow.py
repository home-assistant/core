"""Config flow for the blanco integration."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoAuthError,
    BlancoConnectionError,
    BlancoDeviceTypeError,
    BlancoInvalidTokenError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_APP_ID,
    CONF_APP_LOCALE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_SERVICE_CODE,
    CONF_TOKEN,
    CONF_TOKEN_TYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL): str,
        vol.Required(CONF_SERVICE_CODE): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input by performing the registration and auth requests.

    Returns a dict with the API token and related fields on success.

    Raises:
        BlancoConnectionError: Network failure or unexpected server error.
        BlancoAuthError: Device access not yet granted via the BLANCO UNIT App.
        BlancoInvalidTokenError: Server returned 200 but no token in the response.
        BlancoDeviceTypeError: Device type not supported for smart home use.
    """
    session = async_get_clientsession(hass)
    locale = hass.config.language.split("-")[0][:2]

    client = BlancoApiClient(session, os_version=HA_VERSION)

    # Register the app; app_id is set on the client automatically.
    reg = await client.register_app(locale)

    # Derive dev_id from serial + service code (or use an existing explicit value).
    if CONF_DEV_ID in data:
        dev_id: str = data[CONF_DEV_ID]
    else:
        dev_id = hashlib.sha256(
            (data[CONF_SERIAL] + data[CONF_SERVICE_CODE]).encode()
        ).hexdigest()

    # Authenticate the device; token is stored on the client automatically.
    auth = await client.authenticate(dev_id)

    return {
        "title": data[CONF_SERIAL],
        CONF_TOKEN: auth["token"],
        CONF_TOKEN_TYPE: auth["token_type"],
        CONF_DEV_TYPE: auth["dev_type"],
        CONF_DEV_ID: dev_id,
        CONF_APP_ID: reg["app_id"],
        CONF_APP_LOCALE: locale,
    }


class BlancoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for blanco."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Prevent duplicate entries for the same device.
            await self.async_set_unique_id(user_input[CONF_SERIAL])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except BlancoConnectionError:
                errors["base"] = "cannot_connect"
            except BlancoAuthError:
                errors["base"] = "access_not_granted"
            except BlancoInvalidTokenError:
                errors["base"] = "invalid_auth"
            except BlancoDeviceTypeError:
                errors["base"] = "device_type_not_supported"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_SERIAL: user_input[CONF_SERIAL],
                        CONF_TOKEN: info[CONF_TOKEN],
                        CONF_TOKEN_TYPE: info[CONF_TOKEN_TYPE],
                        CONF_DEV_TYPE: info[CONF_DEV_TYPE],
                        CONF_DEV_ID: info[CONF_DEV_ID],
                        CONF_APP_ID: info[CONF_APP_ID],
                        CONF_APP_LOCALE: info[CONF_APP_LOCALE],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Initiate a re-authentication flow after a token renewal failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with a new service code.

        The serial number is read from the existing config entry so the user
        only needs to supply the service code.
        """
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass,
                    {
                        CONF_SERIAL: reauth_entry.data[CONF_SERIAL],
                        CONF_SERVICE_CODE: user_input[CONF_SERVICE_CODE],
                    },
                )
            except BlancoConnectionError:
                errors["base"] = "cannot_connect"
            except BlancoAuthError:
                errors["base"] = "access_not_granted"
            except BlancoInvalidTokenError:
                errors["base"] = "invalid_auth"
            except BlancoDeviceTypeError:
                errors["base"] = "device_type_not_supported"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_TOKEN: info[CONF_TOKEN],
                        CONF_TOKEN_TYPE: info[CONF_TOKEN_TYPE],
                        CONF_APP_ID: info[CONF_APP_ID],
                        CONF_APP_LOCALE: info[CONF_APP_LOCALE],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_SERVICE_CODE): str}),
            description_placeholders={
                "serial": reauth_entry.data.get(CONF_SERIAL, ""),
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry with new credentials."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except BlancoConnectionError:
                errors["base"] = "cannot_connect"
            except BlancoAuthError:
                errors["base"] = "access_not_granted"
            except BlancoInvalidTokenError:
                errors["base"] = "invalid_auth"
            except BlancoDeviceTypeError:
                errors["base"] = "device_type_not_supported"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_SERIAL: user_input[CONF_SERIAL],
                        CONF_TOKEN: info[CONF_TOKEN],
                        CONF_TOKEN_TYPE: info[CONF_TOKEN_TYPE],
                        CONF_DEV_TYPE: info[CONF_DEV_TYPE],
                        CONF_DEV_ID: info[CONF_DEV_ID],
                        CONF_APP_ID: info[CONF_APP_ID],
                        CONF_APP_LOCALE: info[CONF_APP_LOCALE],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input
                or {CONF_SERIAL: reconfigure_entry.data.get(CONF_SERIAL, "")},
            ),
            errors=errors,
        )


# ── Legacy exception classes ──────────────────────────────────────────────────
# Kept for backward compatibility; no longer raised by this module's own logic.


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class AccessNotGranted(HomeAssistantError):
    """Error to indicate access has not been granted via the BLANCO UNIT App."""


class DeviceTypeNotSupported(HomeAssistantError):
    """Error to indicate the device type is not supported for smart home use."""
