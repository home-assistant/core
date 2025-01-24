"""Config flow for Media Extractor integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class MediaExtractorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Media Extractor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Media extractor", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
