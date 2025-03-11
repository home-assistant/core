"""Add Config Flow."""

import logging

import meraki
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY  # noqa: F401
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MerakiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meraki Network."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial user input (API Key, optional Org ID, optional Network ID)."""
        errors = {}

        if user_input is not None:
            api_key = user_input["api_key"]
            org_id = user_input.get("org_id")
            network_id = user_input.get("network_id")

            try:
                dashboard = meraki.DashboardAPI(api_key=api_key, suppress_logging=True)

                if network_id:
                    await self.hass.async_add_executor_job(
                        dashboard.networks.getNetwork, network_id
                    )
                elif org_id:
                    await self.hass.async_add_executor_job(
                        dashboard.organizations.getOrganization, org_id
                    )
                else:
                    orgs = await self.hass.async_add_executor_job(
                        dashboard.organizations.getOrganizations
                    )
                    if not orgs:
                        errors["base"] = "no_organizations"

            except meraki.APIError as e:
                _LOGGER.error(f"Meraki API Error: {e}")  # noqa: G004
                errors["base"] = "invalid_api_key"

            if not errors:
                return self.async_create_entry(title="Meraki Network", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=self._get_schema(), errors=errors
        )

    def _get_schema(self, default_data=None):
        """Return the schema for the setup form."""
        default_data = default_data or {}
        return vol.Schema(
            {
                vol.Required(
                    "api_key", default=default_data.get("api_key", "")
                ): cv.string,
                vol.Required(
                    "org_id", default=default_data.get("org_id", "")
                ): cv.string,
                vol.Optional(
                    "network_id", default=default_data.get("network_id", "")
                ): cv.string,
            }
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return MerakiOptionsFlowHandler(config_entry)


class MerakiOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Meraki integration."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            api_key = (
                user_input["api_key"]
                if user_input["api_key"]
                else self.config_entry.options.get("api_key")
            )
            org_id = user_input.get("org_id")
            network_id = user_input.get("network_id")

            try:
                dashboard = meraki.DashboardAPI(api_key=api_key, suppress_logging=True)

                if network_id:
                    await self.hass.async_add_executor_job(
                        dashboard.networks.getNetwork, network_id
                    )
                elif org_id:
                    await self.hass.async_add_executor_job(
                        dashboard.organizations.getOrganization, org_id
                    )
                else:
                    orgs = await self.hass.async_add_executor_job(
                        dashboard.organizations.getOrganizations
                    )
                    if not orgs:
                        errors["base"] = "no_organizations"

            except meraki.APIError as e:
                _LOGGER.error(f"Meraki API Error: {e}")  # noqa: G004
                errors["base"] = "invalid_api_key"

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        "api_key": api_key,  # Behalte alten API Key, falls leer
                        "org_id": org_id,
                        "network_id": network_id,
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_schema(self.config_entry.options),
            errors=errors,
        )

    def _get_schema(self, default_data=None):
        """Return the schema for the options form."""
        default_data = default_data or {}
        return vol.Schema(
            {
                vol.Required(
                    "api_key"
                ): cv.string,  # Passwort-Feld, nicht vorausgefüllt
                vol.Required(
                    "org_id", default=default_data.get("org_id", "")
                ): cv.string,
                vol.Optional(
                    "network_id", default=default_data.get("network_id", "")
                ): cv.string,
            }
        )
