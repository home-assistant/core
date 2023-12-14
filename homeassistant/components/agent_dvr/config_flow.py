"""Config flow to configure Agent devices."""
from contextlib import suppress
from typing import Any

from agent import AgentConnectionError, AgentError
from agent.a import Agent
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SERVER_URL
from .helpers import generate_url

DEFAULT_PORT = 8090


class AgentFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Agent config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle an Agent config flow."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            server_origin = generate_url(host, port)
            agent_client = Agent(server_origin, async_get_clientsession(self.hass))

            with suppress(AgentConnectionError, AgentError):
                await agent_client.update()

            await agent_client.close()

            if agent_client.is_available:
                await self.async_set_unique_id(agent_client.unique)

                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        SERVER_URL: server_origin,
                    }
                )

                device_config = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    SERVER_URL: server_origin,
                }

                return self.async_create_entry(
                    title=agent_client.name, data=device_config
                )

            errors["base"] = "cannot_connect"

        data = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data),
            errors=errors,
        )
