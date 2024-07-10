"""Config flow for Weheat."""

import logging

import voluptuous as vol
from weheat_backend_client.abstractions import HeatPumpDiscovery

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import API_URL, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Weheat OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self):
        """Initialize the Weheat OAuth2 flow."""
        super().__init__()

        self._auth_data = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Override the create entry method to change to the step to find the heat pumps."""
        self._auth_data = data

        return await self.async_step_find_devices()

    async def async_step_find_devices(self, info=None) -> ConfigFlowResult:
        """Select the heat pump to control.

        Will skip selection if only one heat pump is found.
        """
        if info is None or "uuid" not in info:
            # nothing select, construct list of devices
            discovered_pumps = await self.hass.async_add_executor_job(
                HeatPumpDiscovery.discover,
                API_URL,
                self._auth_data["token"]["access_token"],
            )

            if len(discovered_pumps) == 0:
                # when there are no pumps, the user is lacking access
                return self.async_abort(reason="no_devices_found")
            if len(discovered_pumps) == 1:
                # just select this pump since it is the only one
                # await self.async_set_unique_id(info["uuid"])
                # self._abort_if_unique_id_configured()
                # # a pump was selected
                # return self.async_create_entry(
                #     title="Weheat heatpump", data=(self._auth_data | info)
                # )
                return self.async_abort(reason="no_devices_found")

            # show list of pumps
            return self.async_show_form(
                step_id="find_devices",
                data_schema=vol.Schema(
                    {vol.Required("uuid"): vol.In(discovered_pumps)}
                ),
            )

        # a heat pump was selected, try adding it
        await self.async_set_unique_id(info["uuid"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Weheat heatpump", data=(self._auth_data | info)
        )
