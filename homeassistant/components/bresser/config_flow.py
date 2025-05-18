"""Config flow for Bresser."""

from __future__ import annotations

import secrets
from typing import Any

from yarl import URL

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class BresserConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    _webhook_id: str
    _host: str
    _port: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is None:
            self._webhook_id = secrets.token_hex(4)
            return self.async_show_form(step_id="user")

        url = URL(get_url(self.hass))
        assert url.host

        self._host = url.host
        self._port = str(url.port)

        return self.async_create_entry(
            title="Bresser Weather Station",
            data={
                CONF_WEBHOOK_ID: self._webhook_id,
                CONF_HOST: self._host,
                CONF_PORT: self._port,
            },
            description_placeholders={
                "host": self._host,
                "port": self._port,
                "path": webhook.async_generate_path(self._webhook_id),
            },
        )
