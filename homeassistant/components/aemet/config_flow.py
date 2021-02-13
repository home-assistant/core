"""Config flow for AEMET OpenData."""
from aemet_opendata import AEMET
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME
from .const import DOMAIN  # pylint:disable=unused-import


class AemetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for AEMET OpenData."""

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            api_online = await _is_aemet_api_online(self.hass, user_input[CONF_API_KEY])
            if not api_online:
                errors["base"] = "invalid_api_key"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


async def _is_aemet_api_online(hass, api_key):
    aemet = AEMET(api_key)
    return await hass.async_add_executor_job(
        aemet.get_conventional_observation_stations, False
    )
