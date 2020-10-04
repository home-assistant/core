"""Config flow to configure Agent devices."""
import logging

from agent import AgentConnectionError, AgentError
from agent.a import Agent
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SERVER_URL  # pylint:disable=unused-import
from .helpers import generate_url

DEFAULT_PORT = 8090
_LOGGER = logging.getLogger(__name__)


class AgentFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Agent config flow."""

    def __init__(self):
        """Initialize the Agent config flow."""
        self.device_config = {}

    async def async_step_user(self, user_input=None):
        """Handle an Agent config flow."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            server_origin = generate_url(host, port)
            agent_client = Agent(server_origin, async_get_clientsession(self.hass))

            try:
                await agent_client.update()
            except AgentConnectionError:
                pass
            except AgentError:
                pass

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

                self.device_config = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    SERVER_URL: server_origin,
                }

                return await self._create_entry(agent_client.name)

            errors["base"] = "device_unavailable"

        data = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            description_placeholders=self.device_config,
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def _create_entry(self, server_name):
        """Create entry for device."""
        return self.async_create_entry(title=server_name, data=self.device_config)
