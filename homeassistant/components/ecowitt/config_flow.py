"""Config flow for ecowitt."""
from __future__ import annotations

import secrets
from typing import Any

from yarl import URL

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class EcowittConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the Ecowitt."""

    VERSION = 1
    _webhook_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            self._webhook_id = secrets.token_hex(16)
            return self.async_show_form(
                step_id="user",
            )

        base_url = URL(get_url(self.hass))
        assert base_url.host

        return self.async_create_entry(
            title="Ecowitt",
            data={
                CONF_WEBHOOK_ID: self._webhook_id,
            },
            description_placeholders={
                "path": webhook.async_generate_path(self._webhook_id),
                "server": base_url.host,
                "port": str(base_url.port),
            },
        )


class InvalidPort(HomeAssistantError):
    """Error to indicate there port is not usable."""
