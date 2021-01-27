"""Config flow for MySensors."""
import logging
from typing import Dict, Optional

from packaging.version import Version, parse as parse_version
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.mqtt import valid_publish_topic, valid_subscribe_topic
from homeassistant.components.mysensors import (
    CONF_DEVICE,
    DEFAULT_BAUD_RATE,
    DEFAULT_TCP_PORT,
    is_persistence_file,
)
import homeassistant.helpers.config_validation as cv

from . import CONF_RETAIN, CONF_VERSION, DEFAULT_VERSION

# pylint: disable=unused-import
from .const import (
    CONF_BAUD_RATE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_ALL,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAY_TYPE_TCP,
    CONF_PERSISTENCE_FILE,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    DOMAIN,
    ConfGatewayType,
)
from .gateway import MQTT_COMPONENT, is_serial_port, is_socket_address, try_connect

_LOGGER = logging.getLogger(__name__)


def _get_schema_common() -> dict:
    """Create a schema with options common to all gateway types."""
    schema = {
        vol.Required(
            CONF_VERSION, default="", description={"suggested_value": DEFAULT_VERSION}
        ): str,
        vol.Optional(
            CONF_PERSISTENCE_FILE,
        ): str,
    }
    return schema


def _validate_version(version: str) -> Dict[str, str]:
    """Validate a version string from the user."""
    errors = {CONF_VERSION: "invalid_version"}
    if not isinstance(parse_version(version), Version):
        return errors
    return {}


class MySensorsConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    async def async_step_import(self, user_input: Optional[Dict[str, str]] = None):
        """Import a config entry.

        This method is called by async_setup and it has already
        prepared the dict to be compatible with what a user would have
        entered from the frontend.
        Therefore we process it as though it came from the frontend.
        """
        if user_input[CONF_DEVICE] == MQTT_COMPONENT:
            user_input[CONF_GATEWAY_TYPE] = CONF_GATEWAY_TYPE_MQTT
        else:
            try:
                await self.hass.async_add_executor_job(
                    is_serial_port, user_input[CONF_DEVICE]
                )
            except vol.Invalid:
                user_input[CONF_GATEWAY_TYPE] = CONF_GATEWAY_TYPE_TCP
            else:
                user_input[CONF_GATEWAY_TYPE] = CONF_GATEWAY_TYPE_SERIAL

        return await self.async_step_user(user_input=user_input)

    async def async_step_user(self, user_input: Optional[Dict[str, str]] = None):
        """Create a config entry from frontend user input."""
        schema = {vol.Required(CONF_GATEWAY_TYPE): vol.In(CONF_GATEWAY_TYPE_ALL)}
        schema = vol.Schema(schema)

        if user_input is not None:
            gw_type = user_input[CONF_GATEWAY_TYPE]
            input_pass = user_input if CONF_DEVICE in user_input else None
            if gw_type == CONF_GATEWAY_TYPE_MQTT:
                return await self.async_step_gw_mqtt(input_pass)
            if gw_type == CONF_GATEWAY_TYPE_TCP:
                return await self.async_step_gw_tcp(input_pass)
            if gw_type == CONF_GATEWAY_TYPE_SERIAL:
                return await self.async_step_gw_serial(input_pass)

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_gw_serial(self, user_input: Optional[Dict[str, str]] = None):
        """Create config entry for a serial gateway."""
        errors = {}
        if user_input is not None:
            errors.update(
                await self.validate_common(CONF_GATEWAY_TYPE_SERIAL, user_input, errors)
            )
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_DEVICE]}", data=user_input
                )

        schema = _get_schema_common()
        schema[
            vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE)
        ] = cv.positive_int
        schema[vol.Required(CONF_DEVICE, default="/dev/ttyACM0")] = str

        schema = vol.Schema(schema)
        return self.async_show_form(
            step_id="gw_serial", data_schema=schema, errors=errors
        )

    async def async_step_gw_tcp(self, user_input: Optional[Dict[str, str]] = None):
        """Create a config entry for a tcp gateway."""
        errors = {}
        if user_input is not None:
            if CONF_TCP_PORT in user_input:
                port: int = user_input[CONF_TCP_PORT]
                if not (0 < port <= 65535):
                    errors[CONF_TCP_PORT] = "port_out_of_range"

            errors.update(
                await self.validate_common(CONF_GATEWAY_TYPE_TCP, user_input, errors)
            )
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_DEVICE]}", data=user_input
                )

        schema = _get_schema_common()
        schema[vol.Required(CONF_DEVICE, default="127.0.0.1")] = str
        # Don't use cv.port as that would show a slider *facepalm*
        schema[vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT)] = vol.Coerce(int)

        schema = vol.Schema(schema)
        return self.async_show_form(step_id="gw_tcp", data_schema=schema, errors=errors)

    async def async_step_gw_mqtt(self, user_input: Optional[Dict[str, str]] = None):
        """Create a config entry for a mqtt gateway."""
        errors = {}
        if user_input is not None:
            user_input[CONF_DEVICE] = MQTT_COMPONENT

            if CONF_TOPIC_IN_PREFIX in user_input:
                try:
                    valid_subscribe_topic(user_input[CONF_TOPIC_IN_PREFIX])
                except vol.Invalid:
                    errors[CONF_TOPIC_IN_PREFIX] = "invalid_subscribe_topic"

            if CONF_TOPIC_OUT_PREFIX in user_input:
                try:
                    valid_publish_topic(user_input[CONF_TOPIC_OUT_PREFIX])
                except vol.Invalid:
                    errors[CONF_TOPIC_OUT_PREFIX] = "invalid_publish_topic"

            errors.update(
                await self.validate_common(CONF_GATEWAY_TYPE_MQTT, user_input, errors)
            )
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_DEVICE]}", data=user_input
                )
        schema = _get_schema_common()
        schema[vol.Required(CONF_RETAIN, default=True)] = bool
        schema[vol.Optional(CONF_TOPIC_IN_PREFIX)] = str
        schema[vol.Optional(CONF_TOPIC_OUT_PREFIX)] = str

        schema = vol.Schema(schema)
        _LOGGER.debug("mysconfigflow mqtt errors: %s", errors)
        return self.async_show_form(
            step_id="gw_mqtt", data_schema=schema, errors=errors
        )

    async def validate_common(
        self,
        gw_type: ConfGatewayType,
        user_input: Optional[Dict[str, str]] = None,
        errors: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Validate parameters common to all gateway types."""
        if errors is None:
            errors = {}
        if user_input is not None:
            errors.update(_validate_version(user_input.get(CONF_VERSION)))

            if gw_type != CONF_GATEWAY_TYPE_MQTT:
                verification_func = (
                    is_socket_address
                    if gw_type == CONF_GATEWAY_TYPE_TCP
                    else is_serial_port
                )
                try:
                    await self.hass.async_add_executor_job(
                        verification_func, user_input.get(CONF_DEVICE)
                    )
                except vol.Invalid:
                    errors[CONF_DEVICE] = (
                        "invalid_ip"
                        if gw_type == CONF_GATEWAY_TYPE_TCP
                        else "invalid_serial"
                    )

            try:
                if CONF_PERSISTENCE_FILE in user_input:
                    is_persistence_file(user_input[CONF_PERSISTENCE_FILE])
            except vol.Invalid:
                errors[CONF_PERSISTENCE_FILE] = "invalid_persistence_file"

            # if no errors so far, try to connect
            if not errors and not await try_connect(self.hass, user_input):
                errors["base"] = "cannot_connect"

        return errors
