"""Config flow for BMW ConnectedDrive integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bimmer_connected.api.authentication import MyBMWAuthentication
from bimmer_connected.api.regions import get_region_from_name
from bimmer_connected.models import MyBMWAPIError, MyBMWAuthError
from httpx import RequestError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_SOURCE, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import DOMAIN
from .const import CONF_ALLOWED_REGIONS, CONF_GCID, CONF_READ_ONLY, CONF_REFRESH_TOKEN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(
                options=CONF_ALLOWED_REGIONS,
                translation_key="regions",
            )
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    auth = MyBMWAuthentication(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        get_region_from_name(data[CONF_REGION]),
    )

    try:
        await auth.login()
    except MyBMWAuthError as ex:
        raise InvalidAuth from ex
    except (MyBMWAPIError, RequestError) as ex:
        raise CannotConnect from ex

    # Return info that you want to store in the config entry.
    retval = {"title": f"{data[CONF_USERNAME]}{data.get(CONF_SOURCE, '')}"}
    if auth.refresh_token:
        retval[CONF_REFRESH_TOKEN] = auth.refresh_token
    if auth.gcid:
        retval[CONF_GCID] = auth.gcid
    return retval


class BMWConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyBMW."""

    VERSION = 1

    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{user_input[CONF_REGION]}-{user_input[CONF_USERNAME]}"

            if not self._reauth_entry:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

            info = None
            try:
                info = await validate_input(self.hass, user_input)
                entry_data = {
                    **user_input,
                    CONF_REFRESH_TOKEN: info.get(CONF_REFRESH_TOKEN),
                    CONF_GCID: info.get(CONF_GCID),
                }
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"

            if info:
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry, data=entry_data
                    )
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self._reauth_entry.entry_id
                        )
                    )
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=info["title"],
                    data=entry_data,
                )

        schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA, self._reauth_entry.data if self._reauth_entry else {}
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BMWOptionsFlow:
        """Return a MyBMW option flow."""
        return BMWOptionsFlow(config_entry)


class BMWOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle a option flow for MyBMW."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_account_options()

    async def async_step_account_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Manually update & reload the config entry after options change.
            # Required as each successful login will store the latest refresh_token
            # using async_update_entry, which would otherwise trigger a full reload
            # if the options would be refreshed using a listener.
            changed = self.hass.config_entries.async_update_entry(
                self.config_entry,
                options=user_input,
            )
            if changed:
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="account_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_READ_ONLY,
                        default=self.config_entry.options.get(CONF_READ_ONLY, False),
                    ): bool,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
