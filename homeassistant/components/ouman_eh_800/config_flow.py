"""Config flow for the Ouman EH-800 integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from ouman_eh_800_api import (
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
    OumanEh800Client,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_USERNAME): TextSelector(),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _normalize_url(url: str) -> str:
    """Reduce URL to scheme://host[:port], discarding any path, query, or fragment."""
    return str(URL(url.strip()).origin())


class OumanEh800ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ouman EH-800."""

    VERSION = 1

    async def _async_try_login(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Test the connection by logging in to the device.

        Returns form errors, empty if the login succeeded.
        """
        client = OumanEh800Client(
            session=async_get_clientsession(self.hass),
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            address=data[CONF_URL],
        )
        try:
            await client.login()
        except OumanClientCommunicationError:
            return {"base": "cannot_connect"}
        except OumanClientAuthenticationError:
            return {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        return {}

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Normalize the URL, check for duplicates and test the connection.

        Mutates user_input to hold the normalized URL. Returns form errors,
        empty if validation succeeded.
        """
        try:
            user_input[CONF_URL] = _normalize_url(user_input[CONF_URL])
        except ValueError:
            return {CONF_URL: "invalid_url"}
        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
        return await self._async_try_login(user_input)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := await self._async_validate_input(user_input)):
                return self.async_create_entry(title="Ouman EH-800", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with the device."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (
                errors := await self._async_try_login(
                    {CONF_URL: reauth_entry.data[CONF_URL], **user_input}
                )
            ):
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA, user_input or reauth_entry.data
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := await self._async_validate_input(user_input)):
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )
