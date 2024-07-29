"""Config flow for Weheat."""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from weheat.abstractions import HeatPumpDiscovery

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import API_URL, DOMAIN, HEAT_PUMP_INFO


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Weheat OAuth2 authentication."""

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None
    _auth_data: dict = {}
    _discovered_pumps: list[HeatPumpDiscovery.HeatPumpInfo] = []

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Override the create entry method to change to the step to find the heat pumps."""
        if self.reauth_entry:
            # on a reauth, preserve the heat pump info
            config_entry = self.hass.config_entries.async_get_entry(
                self.reauth_entry.entry_id
            )
            preserved_data: dict = {}
            if config_entry is not None:
                preserved_data = config_entry.data.get(HEAT_PUMP_INFO) or {}
            self.hass.config_entries.async_update_entry(
                self.reauth_entry, data=(data | {HEAT_PUMP_INFO: preserved_data})
            )
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

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
                    HEAT_PUMP_INFO: self._discovered_pumps[0],
                }

                await self.async_set_unique_id(info["uuid"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Weheat heatpump", data=dict(self._auth_data | info)
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

        info[HEAT_PUMP_INFO] = next(
            (hp for hp in self._discovered_pumps if hp.uuid == info["uuid"]), None
        )

        return self.async_create_entry(
            title="Weheat heatpump", data=(self._auth_data | info)
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
