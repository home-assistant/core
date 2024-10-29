"""Config flow to configure the Azure DevOps integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aioazuredevops.client import DevOpsClient
import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ORG, CONF_PAT, CONF_PROJECT, DOMAIN


class AzureDevOpsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Azure DevOps config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._organization: str | None = None
        self._project: str | None = None
        self._pat: str | None = None

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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

    async def _check_setup(self) -> dict[str, str] | None:
        """Check the setup of the flow."""
        errors: dict[str, str] = {}

        aiohttp_session = async_get_clientsession(self.hass)
        client = DevOpsClient(session=aiohttp_session)

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

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form()

        self._organization = user_input[CONF_ORG]
        self._project = user_input[CONF_PROJECT]
        self._pat = user_input.get(CONF_PAT)

        await self.async_set_unique_id(f"{self._organization}_{self._project}")
        self._abort_if_unique_id_configured()

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_setup_form(errors)
        return self._async_create_entry()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        if entry_data.get(CONF_ORG) and entry_data.get(CONF_PROJECT):
            self._organization = entry_data[CONF_ORG]
            self._project = entry_data[CONF_PROJECT]
        self._pat = entry_data[CONF_PAT]

        self.context["title_placeholders"] = {
            "project_url": f"{self._organization}/{self._project}",
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = await self._check_setup()
            if errors is None:
                self.hass.config_entries.async_update_entry(
                    self._get_reauth_entry(),
                    data={
                        CONF_ORG: self._organization,
                        CONF_PROJECT: self._project,
                        CONF_PAT: self._pat,
                    },
                )
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "project_url": f"{self._organization}/{self._project}"
            },
            data_schema=vol.Schema({vol.Required(CONF_PAT): str}),
            errors=errors or {},
        )

    def _async_create_entry(self) -> ConfigFlowResult:
        """Handle create entry."""
        return self.async_create_entry(
            title=f"{self._organization}/{self._project}",
            data={
                CONF_ORG: self._organization,
                CONF_PROJECT: self._project,
                CONF_PAT: self._pat,
            },
        )
