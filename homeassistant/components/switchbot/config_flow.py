"""Config flow for Switchbot."""
import logging

# pylint: disable=import-error
from bluepy import btle
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE

from .const import ATTR_BOT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _btle_connect(addr) -> None:
    """Try to connect to switchbot device."""

    device = btle.Peripheral()
    device.connect(addr, addrType=btle.ADDR_TYPE_RANDOM)
    device.disconnect()

    return device


class SwitchbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchbot."""

    VERSION = 1

    async def _validate_mac(self, data):
        """Try to connect to Switchbot device and create entry if successful."""
        await self.async_set_unique_id(data[CONF_MAC].replace(":", ""))
        self._abort_if_unique_id_configured()

        # Validate bluetooth device mac.
        try:
            await self.hass.async_add_executor_job(_btle_connect, data[CONF_MAC])

        except btle.BTLEDisconnectError as err:
            raise btle.BTLEDisconnectError(err)

        except ValueError as err:
            raise ValueError from err

        return self.async_create_entry(title=data[CONF_NAME], data=data)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        errors = {}

        if user_input is not None:

            user_input[CONF_SENSOR_TYPE] = ATTR_BOT

            try:
                return await self._validate_mac(user_input)

            except btle.BTLEException:
                errors["base"] = "cannot_connect"

            except ValueError:
                errors["base"] = "invalid_host"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required(CONF_MAC): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        _LOGGER.debug("import config: %s", import_config)

        await self.async_set_unique_id(import_config[CONF_MAC].replace(":", ""))
        self._abort_if_unique_id_configured()

        # Add type to import_config.
        # Currently integration only supports bot.
        # More than one type exists.
        import_config[CONF_SENSOR_TYPE] = ATTR_BOT

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )
