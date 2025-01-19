"""Config flow support for Intergas InComfort integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientResponseError
from incomfortclient import IncomfortError, InvalidHeaterList
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_LEGACY_SETPOINT_STATUS, DOMAIN
from .coordinator import async_connect_gateway

TITLE = "Intergas InComfort/Intouch Lan2RF gateway"

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="admin")
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LEGACY_SETPOINT_STATUS, default=False): BooleanSelector(
            BooleanSelectorConfig()
        )
    }
)

ERROR_STATUS_MAPPING: dict[int, tuple[str, str]] = {
    401: (CONF_PASSWORD, "auth_error"),
    404: ("base", "not_found"),
}


async def async_try_connect_gateway(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, str] | None:
    """Try to connect to the Lan2RF gateway."""
    try:
        await async_connect_gateway(hass, config)
    except InvalidHeaterList:
        return {"base": "no_heaters"}
    except IncomfortError as exc:
        if isinstance(exc.message, ClientResponseError):
            scope, error = ERROR_STATUS_MAPPING.get(
                exc.message.status, ("base", "unknown")
            )
            return {scope: error}
        return {"base": "unknown"}
    except TimeoutError:
        return {"base": "timeout_error"}
    except Exception:  # noqa: BLE001
        return {"base": "unknown"}

    return None


class InComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow to set up an Intergas InComfort boyler and thermostats."""

    _discovered_host: str

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> InComfortOptionsFlowHandler:
        """Get the options flow for this handler."""
        return InComfortOptionsFlowHandler()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a DHCP discovered Intergas Gateway device."""
        self._discovered_host = discovery_info.ip
        self._async_abort_entries_match({CONF_HOST: self._discovered_host})
        unique_id = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._discovered_host})

        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup from discovery."""
        if user_input is not None:
            return await self.async_step_user(
                {
                    CONF_HOST: self._discovered_host,
                }
            )
        return self.async_show_form(
            step_id="dhcp_confirm",
            description_placeholders={CONF_HOST: self._discovered_host},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        data_schema: vol.Schema = CONFIG_SCHEMA
        if is_reconfigure := (self.source == SOURCE_RECONFIGURE):
            reconfigure_entry = self._get_reconfigure_entry()
            data_schema = self.add_suggested_values_to_schema(
                data_schema, reconfigure_entry.data
            )
        if user_input is not None:
            if (
                errors := await async_try_connect_gateway(
                    self.hass,
                    (reconfigure_entry.data | user_input)
                    if is_reconfigure
                    else user_input,
                )
            ) is None:
                if is_reconfigure:
                    return self.async_update_reload_and_abort(
                        reconfigure_entry, data_updates=user_input
                    )
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title=TITLE, data=user_input)
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication and confirmation."""
        errors: dict[str, str] | None = None

        if user_input:
            password: str = user_input[CONF_PASSWORD]

            reauth_entry = self._get_reauth_entry()
            errors = await async_try_connect_gateway(
                self.hass, reauth_entry.data | {CONF_PASSWORD: password}
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration flow."""
        return await self.async_step_user()


class InComfortOptionsFlowHandler(OptionsFlow):
    """Handle InComfort Lan2RF gateway options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            new_options: dict[str, Any] = self.config_entry.options | user_input
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=new_options
            )
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            return self.async_create_entry(data=new_options)

        data_schema = self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA, self.config_entry.options
        )
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
