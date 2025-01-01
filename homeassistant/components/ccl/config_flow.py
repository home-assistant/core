"""Config flow for CCL Electronics."""

from __future__ import annotations

import secrets
from typing import Any

from yarl import URL

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class CCLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    _webhook_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is None:
            self._webhook_id = secrets.token_hex(4)
            return self.async_show_form(step_id="user")

        url = URL(get_url(self.hass))
        assert url.host

        return self.async_create_entry(
            title="CCL Weather Station",
            data={CONF_WEBHOOK_ID: self._webhook_id},
            description_placeholders={
                "host": url.host,
                "port": str(url.port),
                "path": webhook.async_generate_path(self._webhook_id),
            },
        )
