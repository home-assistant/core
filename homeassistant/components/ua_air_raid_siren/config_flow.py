"""Config flow for OpenWeatherMap."""
import aiohttp
from ukrainealarm.client import Client
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_REGION

# from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONFIG_FLOW_VERSION, DOMAIN


class UkraineAirRaidConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OpenWeatherMap."""

    VERSION = CONFIG_FLOW_VERSION

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry):
    #     """Get the options flow for this handler."""
    #     return UkraineAlarmOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            region_id = user_input[CONF_REGION]

            await self.async_set_unique_id(region_id)
            self._abort_if_unique_id_configured()

            try:
                api_online = await _is_ukraine_air_raid_api_online(
                    self.hass, user_input[CONF_API_KEY]
                )
                if not api_online:
                    errors["base"] = "unknown"
            except aiohttp.ClientResponseError as ex:
                errors["base"] = "invalid_api_key" if ex.status == 401 else "unknown"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_REGION], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                # vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_REGION): cv.positive_int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


# class UkraineAlarmOptionsFlow(config_entries.OptionsFlow):
#     """Handle options."""

#     def __init__(self, config_entry):
#         """Initialize options flow."""
#         self.config_entry = config_entry

#     async def async_step_init(self, user_input=None):
#         """Manage the options."""
#         if user_input is not None:
#             return self.async_create_entry(title="", data=user_input)

#         return self.async_show_form(
#             step_id="init",
#             data_schema=self._get_options_schema(),
#         )

#     def _get_options_schema(self):
#         return vol.Schema(
#             {
#                 vol.Optional(
#                     CONF_MODE,
#                     default=self.config_entry.options.get(
#                         CONF_MODE,
#                         self.config_entry.data.get(CONF_MODE, DEFAULT_FORECAST_MODE),
#                     ),
#                 ): vol.In(FORECAST_MODES),
#                 vol.Optional(
#                     CONF_LANGUAGE,
#                     default=self.config_entry.options.get(
#                         CONF_LANGUAGE,
#                         self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
#                     ),
#                 ): vol.In(LANGUAGES),
#             }
#         )


async def _is_ukraine_air_raid_api_online(hass, api_key):
    # !!! hass session?
    async with aiohttp.ClientSession() as session:
        return await Client(session, api_key).get_last_alert_index()
