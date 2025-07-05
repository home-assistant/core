"""Config flow for CCL Electronics."""

from __future__ import annotations

import secrets
from typing import Any

from yarl import URL

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class CCLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        webhook_id = secrets.token_hex(4)

        url = URL(get_url(self.hass))
        assert url.host

        host = url.host
        port = str(url.port)

        if user_input is not None:
            return self.async_create_entry(
                title="CCL Weather Station",
                data={
                    CONF_WEBHOOK_ID: webhook_id,
                    CONF_HOST: host,
                    CONF_PORT: port,
                },
                description_placeholders={
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_PATH: webhook.async_generate_path(webhook_id),
                },
            )

        return self.async_show_form(step_id="user")
