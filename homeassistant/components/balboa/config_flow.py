"""Config flow for Balboa Spa Client integration."""

from __future__ import annotations

import logging
from typing import Any

from pybalboa import SpaClient
from pybalboa.exceptions import SpaConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_SYNC_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SYNC_TIME, default=False): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


async def validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    _LOGGER.debug("Attempting to connect to %s", data[CONF_HOST])
    try:
        async with SpaClient(data[CONF_HOST]) as spa:
            if not await spa.async_configuration_loaded():
                raise CannotConnect
            mac = format_mac(spa.mac_address)
            model = spa.model
    except SpaConnectionError as err:
        raise CannotConnect from err

    return {"title": model, "formatted_mac": mac}


class BalboaSpaClientFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Balboa Spa Client config flow."""

    VERSION = 1

    _host: str
    _model: str

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})

        error = None
        try:
            info = await validate_input({CONF_HOST: discovery_info.ip})
        except CannotConnect:
            error = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            error = "unknown"
        if not error:
            self._host = discovery_info.ip
            self._model = info["title"]
            self.context["title_placeholders"] = {CONF_MODEL: self._model}
            return await self.async_step_discovery_confirm()
        return self.async_abort(reason=error)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            data = {CONF_HOST: self._host}
            return self.async_create_entry(title=self._model, data=data)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={CONF_HOST: self._host},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                info = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    info["formatted_mac"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
