"""Config flow for SpaceX Launches and Starman."""
import logging

from auroranoaa import AuroraForecast
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_THRESHOLD, DEFAULT_NAME, DEFAULT_THRESHOLD, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NOAA Aurora Integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            longitude = user_input[CONF_LONGITUDE]
            latitude = user_input[CONF_LATITUDE]

            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AuroraForecast(session=session)

            try:
                await api.get_forecast_data(longitude, latitude)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{DOMAIN}_{user_input[CONF_LONGITUDE]}_{user_input[CONF_LATITUDE]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Aurora - {name}", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(
                        CONF_LONGITUDE,
                        default=self.hass.config.longitude,
                    ): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=-180, max=180),
                    ),
                    vol.Required(
                        CONF_LATITUDE,
                        default=self.hass.config.latitude,
                    ): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=-90, max=90),
                    ),
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow changes."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_THRESHOLD,
                        default=self.config_entry.options.get(
                            CONF_THRESHOLD, DEFAULT_THRESHOLD
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=0, max=100),
                    ),
                }
            ),
        )
