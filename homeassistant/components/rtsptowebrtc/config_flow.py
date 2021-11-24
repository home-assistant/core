"""Config flow for RTSPtoWebRTC."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DATA_SERVER_URL, DOMAIN


class RTSPToWebRTCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """RTSPtoWebRTC config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the RTSPtoWebRTC server url."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            return self.async_create_entry(
                title="RTSPtoWebRTC",
                data={
                    DATA_SERVER_URL: user_input[DATA_SERVER_URL],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(DATA_SERVER_URL): str}),
        )
