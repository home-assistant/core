"""SFR Box config flow."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): selector.TextSelector(),
    }
)
AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


class SFRBoxFlowHandler(ConfigFlow, domain=DOMAIN):
    """SFR Box config flow."""

    VERSION = 1
    _box: SFRBox

    def __init__(self) -> None:
        """Initialize SFR Box flow."""
        self._config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            box = SFRBox(
                ip=user_input[CONF_HOST], client=async_get_clientsession(self.hass)
            )
            try:
                system_info = await box.system_get_info()
            except SFRBoxError:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "cannot_connect"
            else:
                if TYPE_CHECKING:
                    assert system_info is not None
                await self.async_set_unique_id(system_info.mac_addr)
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                else:
                    self._abort_if_unique_id_configured()
                self._box = box
                self._config.update(user_input)
                return await self.async_step_choose_auth()

        suggested_values: Mapping[str, Any] | None = user_input
        if suggested_values is None and self.source == SOURCE_RECONFIGURE:
            suggested_values = self._get_reconfigure_entry().data
        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, suggested_values)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "sample_ip": "192.168.1.1",
                "sample_url": "https://sfrbox.example.com",
            },
        )

    async def async_step_choose_auth(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="choose_auth",
            menu_options=["auth", "skip_auth"],
        )

    async def async_step_auth(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Check authentication."""
        errors = {}
        if user_input is not None:
            try:
                await self._box.authenticate(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except SFRBoxAuthenticationError:
                errors["base"] = "invalid_auth"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                self._config.update(user_input)
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data=self._config
                    )
                return self.async_create_entry(title="SFR Box", data=self._config)

        suggested_values: Mapping[str, Any] | None = user_input
        if suggested_values is None:
            if self.source == SOURCE_REAUTH:
                suggested_values = self._get_reauth_entry().data
            elif self.source == SOURCE_RECONFIGURE:
                suggested_values = self._get_reconfigure_entry().data

        data_schema = self.add_suggested_values_to_schema(AUTH_SCHEMA, suggested_values)
        return self.async_show_form(
            step_id="auth", data_schema=data_schema, errors=errors
        )

    async def async_step_skip_auth(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Skip authentication."""
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=self._config
            )
        return self.async_create_entry(title="SFR Box", data=self._config)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle failed credentials."""
        self._box = SFRBox(
            ip=entry_data[CONF_HOST], client=async_get_clientsession(self.hass)
        )
        return await self.async_step_auth()

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()
