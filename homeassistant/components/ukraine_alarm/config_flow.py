"""Config flow for Ukraine Alarm."""
import aiohttp
from ukrainealarm.client import Client
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_REGION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONFIG_FLOW_VERSION, DOMAIN


class UkraineAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ukraine Alarm."""

    VERSION = CONFIG_FLOW_VERSION

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            region_id = user_input[CONF_REGION]

            await self.async_set_unique_id(region_id)
            self._abort_if_unique_id_configured()
            websession = async_get_clientsession(self.hass)
            try:
                region = await Client(websession, user_input[CONF_API_KEY]).get_alerts(
                    user_input[CONF_REGION]
                )
                if not region:
                    errors["base"] = "unknown"
            except aiohttp.ClientResponseError as ex:
                errors["base"] = "invalid_api_key" if ex.status == 401 else "unknown"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=region[0]["regionName"], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_REGION): cv.positive_int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
