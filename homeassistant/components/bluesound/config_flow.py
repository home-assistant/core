"""Config flow for bluesound."""

import logging
from typing import Any

from pyblu import Player
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN
from .utils import format_unique_id

_LOGGER = logging.getLogger(__name__)


class BluesoundConfigFlow(ConfigFlow, domain=DOMAIN):
    """Bluesound config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            async with Player(user_input[CONF_HOST], user_input[CONF_PORT]) as player:
                try:
                    sync_status = await player.sync_status(timeout=1)
                except TimeoutError:
                    return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(format_unique_id(user_input[CONF_HOST], user_input[CONF_PORT]))

            return self.async_create_entry(
                title=sync_status.name,
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, description="host"): str,
                    vol.Optional(CONF_PORT, default=11000): int,
                }
            ),
        )
