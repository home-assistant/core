"""Config flow to configure the Azure DevOps integration."""
import logging

from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsServiceError
from msrest.authentication import BasicAuthentication
from msrest.exceptions import ClientRequestError
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

        org = user_input.get(CONF_ORG)
        project = user_input.get(CONF_PROJECT)
        pat = user_input.get(CONF_PAT)

        if user_input.get(CONF_PAT) is None:
            connection = Connection(base_url=f"https://dev.azure.com/{org}")
        else:
            connection = Connection(
                base_url=f"https://dev.azure.com/{org}",
                creds=BasicAuthentication("", project),
            )

        error = await self._test_connection(connection, project)
        if error is not None:
            errors["base"] = error
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=f"{org}/{project}",
            data={CONF_ORG: org, CONF_PROJECT: project, CONF_PAT: pat},
        )

    async def _test_connection(self, connection: Connection, project: str) -> str:
        try:
            core_client = connection.clients.get_core_client()
            core_client.get_project(project)
        except AzureDevOpsServiceError:
            return "authorization_error"
        except ClientRequestError:
            return "connection_error"
        return None
