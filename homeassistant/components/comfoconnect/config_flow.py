"""Config flow for ComfoConnect integration."""
import logging

from pycomfoconnect import Bridge, PyComfoConnectNotAllowed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_SENSORS, CONF_TOKEN
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
from .sensor import ATTR_LABEL, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): vol.All(
            str, vol.Length(min=32, max=32, msg="invalid token")
        ),
        vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): str,
        vol.Optional(CONF_PIN, default=DEFAULT_PIN): int,
    }
)

STEP_SENSOR_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSORS): cv.multi_select(
            {k: sensor_attrs[ATTR_LABEL] for k, sensor_attrs in SENSOR_TYPES.items()}
        )
    }
)


async def validate_input(hass, input_data) -> str:
    """Validate the user input by trying to connect to the ComfoConnect bridge."""
    host = input_data[CONF_HOST]
    bridges = await hass.async_add_executor_job(Bridge.discover, host)
    if not bridges:
        raise ConnectionError()
    ccb = ComfoConnectBridge(
        hass,
        bridge=bridges[0],
        name=input_data[CONF_NAME],
        token=input_data[CONF_TOKEN],
        friendly_name=input_data[CONF_USER_AGENT],
        pin=input_data[CONF_PIN],
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
                self.context["user"] = user_input
                return await self.async_step_sensor_selection()
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_sensor_selection(self, user_input=None):
        """Handle sensor selection step."""
        errors = {}
        unique_id = self.context["unique_id"]
        if self.context["source"] == config_entries.SOURCE_IMPORT:
            user_input = {"sensors": self.context["import_sensors"] or []}
        if user_input is not None:
            data = self.context["user"]
            data["resources"] = user_input["sensors"]
            return self.async_create_entry(
                title=f"ComfoAir {unique_id}",
                data=data,
            )
        return self.async_show_form(
            step_id="sensor_selection",
            data_schema=STEP_SENSOR_SELECTION_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        return await self.async_step_user(import_config)
