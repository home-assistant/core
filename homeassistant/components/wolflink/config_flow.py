"""Config flow for Wolf SmartSet Service integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from httpx import RequestError
import voluptuous as vol
from wolf_comm.token_auth import InvalidAuth, PasswordToLong, PortalUnavailable
from wolf_comm.wolf_client import FetchFailed, WolfClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class WolfLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wolf SmartSet Service."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize with empty username and password."""
        self.username: str | None = None
        self.password: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to get connection parameters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            try:
                wolf_client = WolfClient(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    client=create_async_httpx_client(
                        hass=self.hass, verify_ssl=False, timeout=20
                    ),
                )
                devices = await wolf_client.fetch_system_list()
            except PasswordToLong:
                errors["base"] = "password_too_long"
            except PortalUnavailable, RequestError, FetchFailed:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not devices:
                    return self.async_abort(reason="no_devices")
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                wolf_client = WolfClient(
                    reauth_entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    client=create_async_httpx_client(
                        hass=self.hass, verify_ssl=False, timeout=20
                    ),
                )
                await wolf_client.fetch_system_list()
            except PasswordToLong:
                errors["base"] = "password_too_long"
            except PortalUnavailable, RequestError, FetchFailed:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )
