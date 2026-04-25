"""Config flow for the Hypontech Cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from hyponcloud import AuthenticationError, HyponCloud
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HypontechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hypontech Cloud."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            hypon = HyponCloud(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
            try:
                await hypon.connect()
                admin_info = await hypon.get_admin_info()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except TimeoutError, ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(admin_info.id)
                if self.source == SOURCE_USER:
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME],
                        data=user_input,
                    )
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_user()
