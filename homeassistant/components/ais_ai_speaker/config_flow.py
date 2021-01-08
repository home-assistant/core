"""Config flow for AI Speaker integration."""
import logging

from aisapi.ws import AisWebService
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({"host": str})


class AisDevice:
    """Ais device class."""

    def __init__(self, hass, host):
        """Initialize."""
        self.hass = hass
        self.host = host
        self.web_session = aiohttp_client.async_get_clientsession(self.hass)

    async def get_gate_info(self):
        """Return the ais gate info."""
        ais_ws = AisWebService(self.hass.loop, self.web_session, self.host)
        return await ais_ws.get_gate_info()


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    ais_gate = AisDevice(hass, data["host"])

    ais_gate_info = await ais_gate.get_gate_info()
    if ais_gate_info is None:
        raise InvalidAuth

    product = ais_gate_info["Product"]
    ais_id = ais_gate_info["ais_id"]
    return {"title": f"AI-Speaker {product}", "ais_id": ais_id}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AI Speaker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception %s", error)
            errors["base"] = "unknown"
        else:
            # check if this ais id is already configured
            await self.async_set_unique_id(info["ais_id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
