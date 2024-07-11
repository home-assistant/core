"""Config flow for SMS integration."""

import logging

import gammu
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import CONF_BAUD_SPEED, DEFAULT_BAUD_SPEED, DEFAULT_BAUD_SPEEDS, DOMAIN
from .gateway import create_sms_gateway

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): str,
        vol.Optional(CONF_BAUD_SPEED, default=DEFAULT_BAUD_SPEED): selector.selector(
            {"select": {"options": DEFAULT_BAUD_SPEEDS}}
        ),
    }
)


async def get_imei_from_config(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    device = data[CONF_DEVICE]
    connection_mode = "at"
    baud_speed = data.get(CONF_BAUD_SPEED, DEFAULT_BAUD_SPEED)
    if baud_speed != DEFAULT_BAUD_SPEED:
        connection_mode += baud_speed
    config = {"Device": device, "Connection": connection_mode}
    gateway = await create_sms_gateway(config, hass)
    if not gateway:
        raise CannotConnect
    try:
        imei = await gateway.get_imei_async()
    except gammu.GSMError as err:
        raise CannotConnect from err
    finally:
        await gateway.terminate_async()

    # Return info that you want to store in the config entry.
    return imei


class SMSFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMS integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            try:
                imei = await get_imei_from_config(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(imei)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=imei, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
