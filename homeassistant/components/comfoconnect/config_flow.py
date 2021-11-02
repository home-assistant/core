"""Config flow for ComfoConnect integration."""
import logging
import secrets

from pycomfoconnect import Bridge, PyComfoConnectNotAllowed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_SENSORS, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import STEP_ID_INIT, STEP_ID_USER
import homeassistant.helpers.config_validation as cv

from . import ComfoConnectBridge
from .const import (
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from .sensor import SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass, input_data) -> str:
    """Validate the user input by trying to connect to the ComfoConnect bridge."""
    host = input_data[CONF_HOST]
    bridges = await hass.async_add_executor_job(Bridge.discover, host)
    if not bridges:
        raise ConnectionError(f"No bridges found at host {host}")
    ccb = ComfoConnectBridge(
        hass,
        bridge=bridges[0],
        name=input_data.get(CONF_NAME, DEFAULT_NAME),
        token=input_data.get(CONF_TOKEN, DEFAULT_TOKEN),
        friendly_name=input_data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
        pin=input_data.get(CONF_PIN, DEFAULT_PIN),
    )
    try:
        await ccb.connect()
    finally:
        await ccb.disconnect()
    return ccb.unique_id


class ComfoConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ConfigFlow for ComfoConnect integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        bridges = await self.hass.async_add_executor_job(Bridge.discover)
        if bridges:
            # one or more bridges auto-discovered
            host_field_val = vol.All(str, vol.In([bridge.host for bridge in bridges]))
            host_field_key = vol.Required(CONF_HOST, default=bridges[0].host)
        else:
            # no bridge discovered
            host_field_val = str
            host_field_key = vol.Required(CONF_HOST)
        schema = vol.Schema(
            {
                host_field_key: host_field_val,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_PIN, default=DEFAULT_PIN): int,
            }
        )
        if user_input is not None:
            unique_id = None
            try:
                unique_id = await validate_input(self.hass, user_input)
            except ConnectionError:
                errors[CONF_HOST] = "cannot_connect"
            except PyComfoConnectNotAllowed:
                errors[CONF_PIN] = "invalid_auth"
            # We have to catch a very broad "Exception" here, since that's what
            # pycomfoconnect raises
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            if unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                user_input[CONF_TOKEN] = secrets.token_hex(16)
                user_input[CONF_USER_AGENT] = DEFAULT_USER_AGENT
                self.context[STEP_ID_USER] = user_input
                return await self.async_step_sensor_selection()
        return self.async_show_form(
            step_id=STEP_ID_USER, data_schema=schema, errors=errors
        )

    async def async_step_sensor_selection(self, user_input=None):
        """Handle sensor selection step."""
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SENSORS,
                ): cv.multi_select({sensor.key: sensor.name for sensor in SENSOR_TYPES})
            }
        )
        errors = {}
        unique_id = self.context["unique_id"]
        self._abort_if_unique_id_configured()
        if self.context["source"] == config_entries.SOURCE_IMPORT:
            user_input = {"sensors": self.context["import_sensors"] or []}
        if user_input is not None:
            data = self.context[STEP_ID_USER]
            return self.async_create_entry(
                title=f"ComfoAir {unique_id}",
                data=data,
                options={"sensors": user_input["sensors"]},
            )
        return self.async_show_form(
            step_id="sensor_selection",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle ComfoConnect options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize ComfoConnect options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id=STEP_ID_INIT,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SENSORS,
                        default=self.config_entry.options.get(CONF_SENSORS),
                    ): cv.multi_select(
                        {sensor.key: sensor.name for sensor in SENSOR_TYPES}
                    )
                }
            ),
        )
