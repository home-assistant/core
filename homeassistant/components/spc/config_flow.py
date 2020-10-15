"""Config flow for SPC integration."""
import logging

from pyspcwebgw import SpcWebGateway
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from . import CONF_API_URL, CONF_WS_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_API_URL, description={"suggested_value": "http://<IP>:8088"}
        ): str,
        vol.Required(
            CONF_WS_URL, description={"suggested_value": "ws://<IP>:8088/ws/spc"}
        ): str,
    }
)


class SpcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a SPC config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info["device_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"

            except InvalidUrl:
                errors["base"] = "invalid_url"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


async def validate_input(hass: HomeAssistant, data: dict):
    """Validate user input."""
    if not data[CONF_API_URL].startswith("http") or len(data[CONF_API_URL]) < 8:
        raise InvalidUrl

    if not data[CONF_WS_URL].startswith("ws") or len(data[CONF_WS_URL]) < 6:
        raise InvalidUrl

    session = aiohttp_client.async_get_clientsession(hass)

    client = SpcWebGateway(
        loop=hass.loop,
        session=session,
        api_url=data[CONF_API_URL],
        ws_url=data[CONF_WS_URL],
        async_callback=None,
    )

    if not await client.async_load_parameters():
        raise CannotConnect

    title = f"SPC {client.info['variant']}"

    return {"title": title, "device_id": client.info["sn"]}


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidUrl(exceptions.HomeAssistantError):
    """Error to indicate a specified URL was invalid."""
