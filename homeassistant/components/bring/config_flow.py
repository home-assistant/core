"""Config flow for Bring! integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from bring_api import (
    Bring,
    BringAuthException,
    BringAuthResponse,
    BringRequestException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import BringConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)


class BringConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bring!."""

    VERSION = 1
    reauth_entry: BringConfigEntry
    info: BringAuthResponse

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None and not (
            errors := await self.validate_input(user_input)
        ):
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self.info.get("name") or user_input[CONF_EMAIL], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (errors := await self.validate_input(user_input)):
                return self.async_update_reload_and_abort(
                    self.reauth_entry, data=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values={CONF_EMAIL: self.reauth_entry.data[CONF_EMAIL]},
            ),
            description_placeholders={CONF_NAME: self.reauth_entry.title},
            errors=errors,
        )

    async def validate_input(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        """Auth Helper."""

        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        bring = Bring(session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD])

        try:
            self.info = await bring.login()
        except BringRequestException:
            errors["base"] = "cannot_connect"
        except BringAuthException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(bring.uuid)
        return errors
