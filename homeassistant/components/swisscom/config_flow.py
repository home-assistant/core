"""Config flow for the Swisscom Internet-Box integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from swisscom_internet_box import (
    BoxInfo,
    SwisscomAuthError,
    SwisscomClient,
    SwisscomConnectionError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST, default=DEFAULT_HOST): str,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
)


class SwisscomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swisscom Internet-Box."""

    VERSION = 1

    async def _async_validate_input(
        self, host: str, username: str, password: str
    ) -> tuple[BoxInfo | None, dict[str, str]]:
        """Validate the credentials and return the box info or errors."""
        client = SwisscomClient(
            async_get_clientsession(self.hass), host, username, password
        )
        try:
            await client.login()
            info = await client.get_box_info()
        except SwisscomAuthError:
            return None, {"base": "invalid_auth"}
        except SwisscomConnectionError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception during Swisscom config flow")
            return None, {"base": "unknown"}
        return info, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_validate_input(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if info is not None:
                await self.async_set_unique_id(format_mac(info.base_mac))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.model_name or "Internet-Box", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored password is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            info, errors = await self._async_validate_input(
                reauth_entry.data[CONF_HOST],
                reauth_entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if info is not None:
                await self.async_set_unique_id(format_mac(info.base_mac))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={
                CONF_HOST: reauth_entry.data[CONF_HOST],
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
            },
            errors=errors,
        )
