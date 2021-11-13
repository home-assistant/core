"""Config flow for WebRTC."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DATA_RTSP_TO_WEBRTC_URL, DOMAIN


class WebRTCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """WebRTC config flow."""

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
                    DATA_RTSP_TO_WEBRTC_URL: user_input[DATA_RTSP_TO_WEBRTC_URL],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(DATA_RTSP_TO_WEBRTC_URL): str}),
        )
