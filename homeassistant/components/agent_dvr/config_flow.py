"""Config flow to configure Agent devices."""

from typing import Any, override

from agent import AgentError
from agent.a import Agent
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DOMAIN, SERVER_URL
from .helpers import generate_url

DEFAULT_PORT = 8090


def _entry_data(host: str, port: int) -> dict[str, Any]:
    """Return the config entry data for an Agent DVR server."""
    return {CONF_HOST: host, CONF_PORT: port, SERVER_URL: generate_url(host, port)}


class AgentFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an Agent config flow."""

    _addon_name: str
    _discovered_data: dict[str, Any]
    _discovered_name: str

    async def _async_get_agent(self, host: str, port: int) -> Agent | None:
        """Connect to an Agent DVR server, return None if it can't be reached."""
        agent_client = Agent(
            generate_url(host, port), async_get_clientsession(self.hass)
        )

        try:
            await agent_client.update()
        except AgentError:
            # Also raised when the server refuses the request, for example
            # with Protect API turned on; it then has no status to read.
            return None
        finally:
            await agent_client.close()

        return agent_client

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an Agent config flow."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            if (agent_client := await self._async_get_agent(host, port)) is not None:
                # Don't refuse when the app's discovery of this server is still
                # waiting; creating the entry removes it.
                await self.async_set_unique_id(
                    agent_client.unique, raise_on_progress=False
                )

                entry_data = _entry_data(host, port)
                self._abort_if_unique_id_configured(updates=entry_data)

                return self.async_create_entry(title=agent_client.name, data=entry_data)

            errors["base"] = "cannot_connect"

        data = {
            probatio.Required(CONF_HOST): str,
            probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(data),
            errors=errors,
        )

    @override
    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle the Agent DVR app being discovered by the Supervisor."""
        host = discovery_info.config[CONF_HOST]
        port = discovery_info.config[CONF_PORT]

        # Connect now to get the server's ID, so a server already added by hand
        # isn't offered again.
        if (agent_client := await self._async_get_agent(host, port)) is None:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(agent_client.unique)

        self._discovered_data = _entry_data(host, port)
        self._abort_if_unique_id_configured(updates=self._discovered_data)

        self._discovered_name = agent_client.name
        self._addon_name = discovery_info.name

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the Agent DVR server provided by the app."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name, data=self._discovered_data
            )

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._addon_name},
        )
