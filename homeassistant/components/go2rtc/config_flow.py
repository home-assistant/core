"""Config flow for WebRTC."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


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
