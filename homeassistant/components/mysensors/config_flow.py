"""Config flow for MySensors."""
import asyncio
import hashlib
import logging
from typing import Optional

import async_timeout
from mysensors import BaseAsyncGateway
import voluptuous as vol

from homeassistant.components.mysensors import (
    CONF_DEVICE,
    DEFAULT_BAUD_RATE,
    DEFAULT_TCP_PORT,
    is_persistence_file,
)
import homeassistant.helpers.config_validation as cv

from . import CONF_RETAIN, CONF_VERSION, DEFAULT_VERSION
from ... import config_entries
from ..mqtt import valid_publish_topic, valid_subscribe_topic
from .const import (
    CONF_BAUD_RATE,
    CONF_PERSISTENCE_FILE,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    DOMAIN,
)
from .gateway import MQTT_COMPONENT, _get_gateway, is_serial_port, is_socket_address

_LOGGER = logging.getLogger(__name__)


async def try_connect(hass, user_input, uniqueid: str) -> bool:
    """Try to connect to a gateway and report if it worked."""
    if user_input[CONF_DEVICE] == MQTT_COMPONENT:
        return True  # dont validate mqtt. mqtt gateways dont send ready messages :(
    user_input_copy = user_input.copy()
    try:
        gateway: Optional[BaseAsyncGateway] = await _get_gateway(
            hass, user_input_copy, uniqueid, persistence=False
        )
        if gateway is None:
            return False
        else:
            gateway_ready = asyncio.Future()

            def gateway_ready_callback(msg):
                msg_type = msg.gateway.const.MessageType(msg.type)
                _LOGGER.debug("Received MySensors msg type %s: %s", msg_type.name, msg)
                if msg_type.name != "internal":
                    return
                internal = msg.gateway.const.Internal(msg.sub_type)
                if internal.name != "I_GATEWAY_READY":
                    return
                _LOGGER.debug("Received gateway ready")
                gateway_ready.set_result(True)

            gateway.event_callback = gateway_ready_callback
            connect_task = None
            try:
                connect_task = asyncio.create_task(gateway.start())
                with async_timeout.timeout(5):
                    await gateway_ready
                    return True
            except asyncio.TimeoutError:
                _LOGGER.info("Try gateway connect failed with timeout")
                return False
            finally:
                if connect_task is not None and not connect_task.done():
                    connect_task.cancel()
                asyncio.create_task(gateway.stop())
    except OSError as err:
        _LOGGER.info("Try gateway connect failed with exception", exc_info=err)
        return False


class MySensorsConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    async def async_step_import(self, user_input):
        """Import a config entry.

        This method is called by async_setup and it has already
        prepared the dict to be compatible with what a user would have
        entered from the frontend.
        Therefore we process it as though it came from the frontend.
        """
        return await self.async_step_user(user_input=user_input)

    async def async_step_user(self, user_input=None):
        """Create a config entry from frontend user input."""
        errors = {}
        if user_input is not None:
            is_mqtt = user_input[CONF_DEVICE] == MQTT_COMPONENT
            is_serial = False
            if not is_mqtt:
                try:
                    await self.hass.async_add_executor_job(
                        is_serial_port, user_input[CONF_DEVICE]
                    )
                except vol.Invalid:
                    pass
                else:
                    is_serial = True
                if not is_serial:
                    try:
                        await self.hass.async_add_executor_job(
                            is_socket_address, user_input[CONF_DEVICE]
                        )
                    except vol.Invalid:
                        errors[CONF_DEVICE] = "invalid_device"

            try:
                if is_mqtt and CONF_TOPIC_IN_PREFIX in user_input:
                    valid_subscribe_topic(user_input[CONF_TOPIC_IN_PREFIX])
            except vol.Invalid:
                errors[CONF_TOPIC_IN_PREFIX] = "invalid_subscribe_topic"
            try:
                if is_mqtt and CONF_TOPIC_OUT_PREFIX in user_input:
                    valid_publish_topic(user_input[CONF_TOPIC_OUT_PREFIX])
            except vol.Invalid:
                errors[CONF_TOPIC_OUT_PREFIX] = "invalid_publish_topic"
            if not is_mqtt and (
                CONF_TCP_PORT in user_input
                and (user_input[CONF_TCP_PORT] < 1 or user_input[CONF_TCP_PORT] > 65535)
            ):
                errors[CONF_TCP_PORT] = "invalid_port"
            try:
                if CONF_PERSISTENCE_FILE in user_input:
                    is_persistence_file(user_input[CONF_PERSISTENCE_FILE])
            except vol.Invalid:
                errors[CONF_TCP_PORT] = "invalid_persistence_file"

            uniquestr = user_input[CONF_DEVICE]
            if is_mqtt:
                uniquestr += (
                    user_input[CONF_TOPIC_IN_PREFIX] + user_input[CONF_TOPIC_OUT_PREFIX]
                )
            elif not is_serial:
                uniquestr += str(user_input[CONF_TCP_PORT])
            gateway_id = hashlib.sha256(uniquestr.encode()).hexdigest()[:8]
            await self.async_set_unique_id(gateway_id)
            self._abort_if_unique_id_configured()

            # if no errors so far, try to connect
            if not errors and not await try_connect(
                self.hass, user_input, uniqueid=gateway_id
            ):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_DEVICE]}", data=user_input
                )

        schema = dict()
        schema[vol.Optional(CONF_RETAIN, default=True)] = bool
        schema[
            vol.Required(CONF_VERSION, description={"suggested_value": DEFAULT_VERSION})
        ] = str

        schema[vol.Required(CONF_DEVICE, default="127.0.0.1")] = str
        # schema[vol.Optional(CONF_PERSISTENCE_FILE)] = str
        schema[
            vol.Optional(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE)
        ] = cv.positive_int
        schema[vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT)] = vol.Range(
            min=1, max=65535
        )
        schema[vol.Optional(CONF_TOPIC_IN_PREFIX)] = str
        schema[vol.Optional(CONF_TOPIC_OUT_PREFIX)] = str

        schema = vol.Schema(schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
