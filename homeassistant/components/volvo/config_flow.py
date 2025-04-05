"""Config flow for Volvo."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .api import ConfigFlowVolvoAuth
from .const import (
    CONF_VIN,
    DOMAIN,
    MANUFACTURER,
    OPT_FUEL_CONSUMPTION_UNIT,
    OPT_FUEL_UNIT_LITER_PER_100KM,
    OPT_FUEL_UNIT_MPG_UK,
    OPT_FUEL_UNIT_MPG_US,
)
from .coordinator import VolvoConfigEntry, VolvoData
from .volvo_connected.api import VolvoCarsApi
from .volvo_connected.models import VolvoApiException

_LOGGER = logging.getLogger(__name__)


def _default_fuel_unit(hass: HomeAssistant) -> str:
    if hass.config.country == "UK":
        return OPT_FUEL_UNIT_MPG_UK

    if hass.config.units == US_CUSTOMARY_SYSTEM or hass.config.country == "US":
        return OPT_FUEL_UNIT_MPG_US

    return OPT_FUEL_UNIT_LITER_PER_100KM


class VolvoOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Volvo OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize Volvo config flow."""
        super().__init__()

        self._vins: list[str] = []
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

    # Overridden method
    @staticmethod
    @callback
    def async_get_options_flow(_: VolvoConfigEntry) -> VolvoOptionsFlowHandler:
        """Create the options flow."""
        return VolvoOptionsFlowHandler()

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
            api = VolvoCarsApi(web_session, auth, "", user_input[CONF_API_KEY])

            try:
                self._vins = await api.async_get_vehicles()
            except VolvoApiException:
                _LOGGER.exception("Unable to retrieve vehicles")
                errors["base"] = "cannot_load_vehicles"

            if not errors:
                self._config_data |= user_input

                if len(self._vins) == 1:
                    # If there is only one VIN, take that as value and
                    # immediately create the entry. No need to show
                    # additional step.
                    self._config_data[CONF_VIN] = self._vins[0]
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

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                ): str,
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

        schema = vol.Schema(
            {
                vol.Required(CONF_VIN): SelectSelector(
                    SelectSelectorConfig(
                        options=self._vins,
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
            options={OPT_FUEL_CONSUMPTION_UNIT: _default_fuel_unit(self.hass)},
        )


class VolvoOptionsFlowHandler(OptionsFlow):
    """Class to handle the options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        if TYPE_CHECKING:
            assert isinstance(self.config_entry.runtime_data, VolvoData)

        coordinator = self.config_entry.runtime_data.coordinator
        schema: dict[vol.Marker, Any] = {}

        if coordinator.vehicle.has_combustion_engine():
            schema.update(
                {
                    vol.Required(
                        OPT_FUEL_CONSUMPTION_UNIT,
                        default=self.config_entry.options.get(
                            OPT_FUEL_CONSUMPTION_UNIT, OPT_FUEL_UNIT_LITER_PER_100KM
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                OPT_FUEL_UNIT_LITER_PER_100KM,
                                OPT_FUEL_UNIT_MPG_UK,
                                OPT_FUEL_UNIT_MPG_US,
                            ],
                            multiple=False,
                            translation_key=OPT_FUEL_CONSUMPTION_UNIT,
                        )
                    )
                }
            )

        if len(schema) == 0:
            return self.async_abort(reason="no_options_available")

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), self.config_entry.options
            ),
        )
