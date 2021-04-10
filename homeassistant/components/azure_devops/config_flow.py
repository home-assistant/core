"""Config flow to configure the Azure DevOps integration."""
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


class AzureDevOpsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Azure DevOps config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize config flow."""
        self._organization = None
        self._project = None
        self._pat = None

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORG, default=self._organization): str,
                    vol.Required(CONF_PROJECT, default=self._project): str,
                    vol.Optional(CONF_PAT): str,
                }
            ),
            errors=errors or {},
        )

    async def _show_reauth_form(self, errors=None):
        """Show the reauth form to the user."""
        return self.async_show_form(
            step_id="reauth",
            description_placeholders={
                "project_url": f"{self._organization}/{self._project}"
            },
            data_schema=vol.Schema({vol.Required(CONF_PAT): str}),
            errors=errors or {},
        )

    async def _check_setup(self):
        """Check the setup of the flow."""
        errors = {}

        client = DevOpsClient()

        try:
            if self._pat is not None:
                await client.authorize(self._pat, self._organization)
                if not client.authorized:
                    errors["base"] = "invalid_auth"
                    return errors
            project_info = await client.get_project(self._organization, self._project)
            if project_info is None:
                errors["base"] = "project_error"
                return errors
        except aiohttp.ClientError:
            errors["base"] = "cannot_connect"
            return errors
        return None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._organization = user_input[CONF_ORG]
        self._project = user_input[CONF_PROJECT]
        self._pat = user_input.get(CONF_PAT)

        await self.async_set_unique_id(f"{self._organization}_{self._project}")
        self._abort_if_unique_id_configured()

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_setup_form(errors)
        return self._async_create_entry()

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        if user_input.get(CONF_ORG) and user_input.get(CONF_PROJECT):
            self._organization = user_input[CONF_ORG]
            self._project = user_input[CONF_PROJECT]
        self._pat = user_input[CONF_PAT]

        self.context["title_placeholders"] = {
            "project_url": f"{self._organization}/{self._project}",
        }

        await self.async_set_unique_id(f"{self._organization}_{self._project}")

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_reauth_form(errors)

        entry = await self.async_set_unique_id(self.unique_id)
        self.hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_ORG: self._organization,
                CONF_PROJECT: self._project,
                CONF_PAT: self._pat,
            },
        )
        return self.async_abort(reason="reauth_successful")

    def _async_create_entry(self):
        """Handle create entry."""
        return self.async_create_entry(
            title=f"{self._organization}/{self._project}",
            data={
                CONF_ORG: self._organization,
                CONF_PROJECT: self._project,
                CONF_PAT: self._pat,
            },
        )
