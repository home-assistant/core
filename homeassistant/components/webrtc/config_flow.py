"""Config flow for WebRTC."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import CONF_STUN_SERVERS, DOMAIN


class WebRTCConfigFlow(ConfigFlow, domain=DOMAIN):
    """WebRTC config flow."""

    _hassio_discovery: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the RTSPtoWebRTC server url."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(DOMAIN)
        return self.async_create_entry(title="WebRTC", data={})

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> WebRTCOptionsFlow:
        """Create an options flow."""
        return WebRTCOptionsFlow(config_entry)


class WebRTCOptionsFlow(OptionsFlowWithConfigEntry):
    """WebRTC Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_STUN_SERVERS): TextSelector(
                            TextSelectorConfig(multiple=True)
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
