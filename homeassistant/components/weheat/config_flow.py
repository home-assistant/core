"""Config flow for Weheat."""

import logging

import voluptuous as vol
from weheat.abstractions import HeatPumpDiscovery

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
        self._discovered_pumps = None

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
            self._discovered_pumps = await self.hass.async_add_executor_job(
                HeatPumpDiscovery.discover,
                API_URL,
                self._auth_data["token"]["access_token"],
            )

            if len(self._discovered_pumps) == 0:
                # when there are no pumps, the user is lacking access
                return self.async_abort(reason="no_devices_found")
            if len(self._discovered_pumps) == 1:
                # just select this pump since it is the only one
                info = {
                    "uuid": self._discovered_pumps[0].uuid,
                    "heat_pump_info": self._discovered_pumps[0],
                }

                await self.async_set_unique_id(info["uuid"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Weheat heatpump", data=(self._auth_data | info)
                )

            # show list of pumps
            heat_pump_dict = {
                hp.uuid: f"{hp.name} ({hp.sn})" for hp in self._discovered_pumps
            }
            return self.async_show_form(
                step_id="find_devices",
                data_schema=vol.Schema({vol.Required("uuid"): vol.In(heat_pump_dict)}),
            )

        # a heat pump was selected, try adding it
        await self.async_set_unique_id(info["uuid"])
        self._abort_if_unique_id_configured()

        info["heat_pump_info"] = next(
            (hp for hp in self._discovered_pumps if hp.uuid == info["uuid"]), None
        )

        return self.async_create_entry(
            title="Weheat heatpump", data=(self._auth_data | info)
        )
