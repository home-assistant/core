"""Config flow for the sma integration."""
import logging

import aiohttp
import pysma
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CUSTOM,
    CONF_FACTOR,
    CONF_GROUP,
    CONF_KEY,
    CONF_UNIT,
    DEVICE_INFO,
    GROUPS,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data: dict):
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL])

    protocol = "https" if data[CONF_SSL] else "http"
    url = f"{protocol}://{data[CONF_HOST]}"

    sma = pysma.SMA(session, url, data[CONF_PASSWORD], group=data[CONF_GROUP])

    if await sma.new_session() is False:
        raise InvalidAuth

    device_info = await sma.device_info()

    if not device_info:
        raise CannotRetrieveDeviceInfo

    await sma.close_session()
    return device_info


class SmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._data = {
            CONF_HOST: vol.UNDEFINED,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_GROUP: GROUPS[0],
            CONF_PASSWORD: vol.UNDEFINED,
            CONF_SENSORS: [],
            CONF_CUSTOM: {},
            DEVICE_INFO: {},
        }

    async def async_step_user(self, user_input=None):
        """First step in config flow."""
        errors = {}
        if user_input is not None:
            self._data[CONF_HOST] = user_input[CONF_HOST]
            self._data[CONF_SSL] = user_input[CONF_SSL]
            self._data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
            self._data[CONF_GROUP] = user_input[CONF_GROUP]
            self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            try:
                self._data[DEVICE_INFO] = await validate_input(self.hass, user_input)
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotRetrieveDeviceInfo:
                errors["base"] = "cannot_retrieve_device_info"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(self._data[DEVICE_INFO]["serial"])
                self._abort_if_unique_id_configured()
                return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._data[CONF_HOST]): cv.string,
                    vol.Optional(CONF_SSL, default=self._data[CONF_SSL]): cv.boolean,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=self._data[CONF_VERIFY_SSL]
                    ): cv.boolean,
                    vol.Optional(CONF_GROUP, default=self._data[CONF_GROUP]): vol.In(
                        GROUPS
                    ),
                    vol.Required(
                        CONF_PASSWORD, default=self._data[CONF_PASSWORD]
                    ): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_sensors(self, user_input=None):
        """Second step in config flow to select sensors to create."""
        errors = {}
        if user_input is not None:
            self._data[CONF_SENSORS] = user_input[CONF_SENSORS]

            if user_input.get("add_custom", False):
                return await self.async_step_custom_sensor()

            return self.async_create_entry(title=self._data[CONF_HOST], data=self._data)

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SENSORS, default=self._data[CONF_SENSORS]
                    ): cv.multi_select({s.name: s.name for s in pysma.Sensors()}),
                    vol.Optional("add_custom"): cv.boolean,
                }
            ),
            errors=errors,
        )

    async def async_step_custom_sensor(self, user_input=None):
        """Third step in config flow to create custom sensors."""
        errors = {}
        if user_input is not None:
            self._data[CONF_CUSTOM][user_input[CONF_NAME]] = {
                CONF_KEY: user_input[CONF_KEY],
                CONF_UNIT: user_input[CONF_UNIT],
                CONF_FACTOR: user_input.get(CONF_FACTOR, 1),
                CONF_PATH: user_input.get(CONF_PATH),
            }

            if user_input.get("add_another", False):
                return await self.async_step_custom_sensor()

            return self.async_create_entry(title=self._data[CONF_HOST], data=self._data)

        return self.async_show_form(
            step_id="custom_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_KEY): vol.All(
                        cv.string, vol.Length(min=13, max=15)
                    ),
                    vol.Required(CONF_UNIT): cv.string,
                    vol.Optional(CONF_FACTOR, default=1): vol.Coerce(float),
                    vol.Optional(CONF_PATH): cv.string,
                    vol.Optional("add_another"): cv.boolean,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config=None):
        """Import a config flow from configuration."""
        device_info = await validate_input(self.hass, import_config)
        await self.async_set_unique_id(device_info["serial"])
        self._abort_if_unique_id_configured(import_config)

        import_config[DEVICE_INFO] = device_info
        return self.async_create_entry(
            title=import_config[CONF_HOST], data=import_config
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotRetrieveDeviceInfo(exceptions.HomeAssistantError):
    """Error to indicate we cannot retrieve the device information."""
