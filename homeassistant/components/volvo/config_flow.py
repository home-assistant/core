"""Config flow for Volvo."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoApiException, VolvoCarsVehicle

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, CONF_NAME, CONF_TOKEN
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api import ConfigFlowVolvoAuth
from .const import CONF_VIN, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class VolvoOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Volvo OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize Volvo config flow."""
        super().__init__()

        self._vehicles: list[VolvoCarsVehicle] = []
        self._config_data: dict = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    # Overridden method
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""
        self._config_data |= data
        return await self.async_step_api_key()

    # By convention method
    async def async_step_reauth(self, _: Mapping[str, Any]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    # By convention method
    async def async_step_reconfigure(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the entry."""
        return await self.async_step_api_key()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={CONF_NAME: self._get_reauth_entry().title},
            )
        return await self.async_step_user()

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the API key step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            web_session = aiohttp_client.async_get_clientsession(self.hass)
            token = self._config_data[CONF_TOKEN][CONF_ACCESS_TOKEN]
            auth = ConfigFlowVolvoAuth(web_session, token)
            api = VolvoCarsApi(web_session, auth, user_input[CONF_API_KEY])

            try:
                await self._async_load_vehicles(api)
            except VolvoApiException:
                _LOGGER.exception("Unable to retrieve vehicles")
                errors["base"] = "cannot_load_vehicles"

            if not errors:
                self._config_data |= user_input

                if len(self._vehicles) == 1:
                    # If there is only one VIN, take that as value and
                    # immediately create the entry. No need to show
                    # additional step.
                    self._config_data[CONF_VIN] = self._vehicles[0].vin
                    return await self._async_create_or_update()

                if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
                    # Don't let users change the VIN. The entry should be
                    # recreated if they want to change the VIN.
                    return await self._async_create_or_update()

                return await self.async_step_vin()

        if user_input is None:
            if self.source == SOURCE_REAUTH:
                user_input = self._config_data = dict(self._get_reauth_entry().data)
            elif self.source == SOURCE_RECONFIGURE:
                user_input = self._config_data = dict(
                    self._get_reconfigure_entry().data
                )
            else:
                user_input = {}

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            {
                CONF_API_KEY: user_input.get(CONF_API_KEY, ""),
            },
        )

        return self.async_show_form(
            step_id="api_key", data_schema=schema, errors=errors
        )

    async def async_step_vin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the VIN step."""
        if user_input is not None:
            self._config_data |= user_input
            return await self._async_create_or_update()

        self._vehicles[0]
        schema = vol.Schema(
            {
                vol.Required(CONF_VIN): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=v.vin,
                                label=f"{v.description.model} ({v.vin})",
                            )
                            for v in self._vehicles
                        ],
                        multiple=False,
                    )
                ),
            },
        )

        return self.async_show_form(step_id="vin", data_schema=schema)

    async def _async_create_or_update(self) -> ConfigFlowResult:
        vin = self._config_data[CONF_VIN]
        await self.async_set_unique_id(vin)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=self._config_data,
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=self._config_data,
                reload_even_if_entry_is_unchanged=False,
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{MANUFACTURER} {vin}",
            data=self._config_data,
        )

    async def _async_load_vehicles(self, api: VolvoCarsApi) -> None:
        self._vehicles = []
        vins = await api.async_get_vehicles()

        for vin in vins:
            vehicle = await api.async_get_vehicle_details(vin)

            if vehicle:
                self._vehicles.append(vehicle)
