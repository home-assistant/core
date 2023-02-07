"""Config flow for the Open Thread Border Router integration."""
from __future__ import annotations

import python_otbr_api
import voluptuous as vol

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class OTBRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Thread Border Router."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Set up by user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            api = python_otbr_api.OTBR(url, async_get_clientsession(self.hass), 10)
            try:
                await api.get_active_dataset_tlvs()
            except python_otbr_api.OTBRError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                return self.async_create_entry(
                    title="Open Thread Border Router",
                    data=user_input,
                )

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle hassio discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        config = discovery_info.config
        url = f"http://{config['host']}:{config['port']}"
        await self.async_set_unique_id(DOMAIN)
        return self.async_create_entry(
            title="Open Thread Border Router",
            data={"url": url},
        )
