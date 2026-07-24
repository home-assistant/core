"""Config flow for the OpenWrt (ubus) integration."""

from typing import Any, override

from openwrt.ubus import Ubus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_DHCP_SOFTWARE, DEFAULT_DHCP_SOFTWARE, DHCP_SOFTWARES, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE): SelectSelector(
            SelectSelectorConfig(
                options=DHCP_SOFTWARES,
                translation_key="dhcp_software",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


def validate_connection(data: dict[str, Any]) -> None:
    """Validate that we can log in to the router with the given configuration."""
    ubus = Ubus(
        f"http://{data[CONF_HOST]}/ubus",
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )
    try:
        session_id = ubus.connect()
    except PermissionError as err:
        raise InvalidAuth from err
    except (ConnectionError, TypeError) as err:
        # openwrt-ubus-rpc raises TypeError when the HTTP request itself fails.
        raise CannotConnect from err
    if session_id is None:
        raise InvalidAuth


class UbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenWrt (ubus)."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self.hass.async_add_executor_job(validate_connection, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            await self.hass.async_add_executor_job(validate_connection, import_data)
        except CannotConnect, InvalidAuth:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title=import_data[CONF_HOST], data=import_data)


class CannotConnect(Exception):
    """Error to indicate we cannot connect to the router."""


class InvalidAuth(Exception):
    """Error to indicate the credentials are invalid."""
