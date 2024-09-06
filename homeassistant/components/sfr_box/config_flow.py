"""SFR Box config flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

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
    _config: dict[str, Any] = {}
    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            box = SFRBox(ip=user_input[CONF_HOST], client=get_async_client(self.hass))
            try:
                system_info = await box.system_get_info()
            except SFRBoxError:
                errors["base"] = "cannot_connect"
            else:
                if TYPE_CHECKING:
                    assert system_info is not None
                await self.async_set_unique_id(system_info.mac_addr)
                self._abort_if_unique_id_configured()
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                self._box = box
                self._config.update(user_input)
                return await self.async_step_choose_auth()

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
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
                if reauth_entry := self._reauth_entry:
                    data = {**reauth_entry.data, **user_input}
                    self.hass.config_entries.async_update_entry(reauth_entry, data=data)
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(reauth_entry.entry_id)
                    )
                    return self.async_abort(reason="reauth_successful")
                self._config.update(user_input)
                return self.async_create_entry(title="SFR Box", data=self._config)

        suggested_values: Mapping[str, Any] | None = user_input
        if self._reauth_entry and not suggested_values:
            suggested_values = self._reauth_entry.data

        data_schema = self.add_suggested_values_to_schema(AUTH_SCHEMA, suggested_values)
        return self.async_show_form(
            step_id="auth", data_schema=data_schema, errors=errors
        )

    async def async_step_skip_auth(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Skip authentication."""
        return self.async_create_entry(title="SFR Box", data=self._config)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle failed credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._box = SFRBox(ip=entry_data[CONF_HOST], client=get_async_client(self.hass))
        return await self.async_step_auth()
