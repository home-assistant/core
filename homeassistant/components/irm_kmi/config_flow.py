"""Config flow to set up IRM KMI integration via the UI."""

import logging

from irm_kmi_api import IrmKmiApiClient, IrmKmiApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_LOCATION, CONF_ZONE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LANGUAGE_OVERRIDE,
    CONF_LANGUAGE_OVERRIDE_OPTIONS,
    DOMAIN,
    HOME_LOCATION_NAME,
    OUT_OF_BENELUX,
    USER_AGENT,
)
from .types import IrmKmiConfigEntry
from .utils import get_config_value

_LOGGER = logging.getLogger(__name__)


class IrmKmiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for the IRM KMI integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: IrmKmiConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return IrmKmiOptionFlow()

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Define the user step of the configuration flow."""
        errors: dict = {}

        home_location = {
            ATTR_LATITUDE: self.hass.config.latitude,
            ATTR_LONGITUDE: self.hass.config.longitude,
        }

        if user_input:
            _LOGGER.debug("Provided config user is: %s", user_input)

            lat: float = user_input[CONF_LOCATION][ATTR_LATITUDE]
            lon: float = user_input[CONF_LOCATION][ATTR_LONGITUDE]

            api_data = {}
            try:
                api_data = await IrmKmiApiClient(
                    session=async_get_clientsession(self.hass),
                    user_agent=USER_AGENT,
                ).get_forecasts_coord({"lat": lat, "long": lon})
            except IrmKmiApiError:
                errors["base"] = "api_error"
                _LOGGER.exception(
                    "Encountered an unexpected error while configuring the integration"
                )

            if api_data.get("cityName", None) in OUT_OF_BENELUX:
                errors[CONF_ZONE] = "out_of_benelux"

            if not errors:
                await self.async_set_unique_id(f"{lat}-{lon}")
                self._abort_if_unique_id_configured()

                name: str = api_data.get("cityName", "")
                if user_input[CONF_LOCATION] == home_location:
                    name = HOME_LOCATION_NAME

                return self.async_create_entry(title=name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_LOCATION, default=home_location): LocationSelector()}
            ),
            errors=errors,
        )


class IrmKmiOptionFlow(OptionsFlow):
    """Option flow for the IRM KMI integration, help change the options once the integration was configured."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("Provided config user is: %s", user_input)
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LANGUAGE_OVERRIDE,
                        default=get_config_value(
                            self.config_entry, CONF_LANGUAGE_OVERRIDE, "none"
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=CONF_LANGUAGE_OVERRIDE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_LANGUAGE_OVERRIDE,
                        )
                    )
                }
            ),
        )
