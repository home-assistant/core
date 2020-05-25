"""Config flow to configure the Azure DevOps integration."""
import logging

from aioazuredevops.client import DevOpsClient
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.azure_devops.const import (
    CONF_ORG,
    CONF_PAT,
    CONF_PROJECT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlow

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class AzureDevOpsFlowHandler(ConfigFlow):
    """Handle a Azure DevOps config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Azure DevOps flow."""

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORG): str,
                    vol.Required(CONF_PROJECT): str,
                    vol.Optional(CONF_PAT): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}

        organization = user_input.get(CONF_ORG)
        project = user_input.get(CONF_PROJECT)
        pat = user_input.get(CONF_PAT)

        client = DevOpsClient()

        try:
            if (
                pat is not None
                and await client.authorize(pat, organization) is not True
            ):
                errors["base"] = "authorization_error"
                return await self._show_setup_form(errors)
            await client.get_project(organization, project)
        except aiohttp.ClientError:
            errors["base"] = "connection_error"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=f"{organization}/{project}",
            data={CONF_ORG: organization, CONF_PROJECT: project, CONF_PAT: pat},
        )
