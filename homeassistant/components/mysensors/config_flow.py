import asyncio
import logging

from mysensors import BaseAsyncGateway

from homeassistant.components.mysensors import CONF_DEVICE, NODE_SCHEMA, DEFAULT_BAUD_RATE, DEFAULT_TCP_PORT, \
    CONF_NODE_NAME, is_persistence_file

from .const import DOMAIN, CONF_PERSISTENCE_FILE, CONF_BAUD_RATE, CONF_TCP_PORT, CONF_TOPIC_IN_PREFIX, \
    CONF_TOPIC_OUT_PREFIX, CONF_NODES
from collections import OrderedDict
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import hashlib
import async_timeout

from typing import Optional

from ..mqtt import valid_subscribe_topic, valid_publish_topic
from ... import config_entries
from ...config_entries import ConfigEntry
from ...core import callback
from .gateway import _get_gateway, MQTT_COMPONENT, is_serial_port, is_socket_address
from . import CONFIG_SCHEMA, CONF_VERSION, CONF_GATEWAYS, CONF_RETAIN, CONF_PERSISTENCE, CONF_OPTIMISTIC, GATEWAY_SCHEMA, DEFAULT_VERSION
from ...data_entry_flow import RESULT_TYPE_CREATE_ENTRY

_LOGGER = logging.getLogger(__name__)


async def try_connect(hass, user_input, uniqueid):
    if user_input[CONF_DEVICE]==MQTT_COMPONENT:
        return True#dont validate mqtt. mqtt gateways dont send ready messages :(
    else:
        u = user_input.copy()
        u[CONF_PERSISTENCE] = False
        try:
            gw: Optional[BaseAsyncGateway] = await _get_gateway(hass, u, uniqueid)
            if gw is None:
                return False
            else:
                gateway_ready = asyncio.Future()

                def gateway_ready_callback(msg):
                    msg_type = msg.gateway.const.MessageType(msg.type)
                    _LOGGER.debug("received mys msg type %s: %s", msg_type.name, msg)
                    if msg_type.name == "internal":
                        internal = msg.gateway.const.Internal(msg.sub_type)
                        if internal.name == "I_GATEWAY_READY":
                            _LOGGER.debug("received gateway ready")
                            gateway_ready.set_result(True)

                gw.event_callback = gateway_ready_callback
                connect_task = None
                try:
                    connect_task = hass.loop.create_task(gw.start())
                    with async_timeout.timeout(5):
                        await gateway_ready
                        return True
                except asyncio.TimeoutError:
                    _LOGGER.info("try_connect failed with timeout")
                    return False
                finally:
                    if connect_task is not None and not connect_task.done():
                        connect_task.cancel()
                    asyncio.create_task(gw.stop())
        except Exception as e:
            _LOGGER.info("try_connect failed with exception", exc_info=e)
            return False



class MySensorsConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return await self.async_step_user(user_input=user_input)


    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            is_mqtt = user_input[CONF_DEVICE] == MQTT_COMPONENT
            is_serial = False
            try:
                if user_input[CONF_DEVICE]!=MQTT_COMPONENT:
                    try:
                        await self.hass.async_add_executor_job(is_serial_port, user_input[CONF_DEVICE])
                        is_serial = True
                    except vol.Invalid:
                        await self.hass.async_add_executor_job(is_socket_address, user_input[CONF_DEVICE])
                        is_serial = False
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
            if not is_mqtt and (CONF_TCP_PORT in user_input and (user_input[CONF_TCP_PORT] < 1 or user_input[CONF_TCP_PORT] > 65535)):
                errors[CONF_TCP_PORT] = "invalid_port"
            try:
                if CONF_PERSISTENCE_FILE in user_input:
                    is_persistence_file(user_input[CONF_PERSISTENCE_FILE])
            except vol.Invalid:
                errors[CONF_TCP_PORT] = "invalid_persistence_file"

            uniquestr = user_input[CONF_DEVICE]
            if is_mqtt:
                uniquestr += user_input[CONF_TOPIC_IN_PREFIX] + user_input[CONF_TOPIC_OUT_PREFIX]
            elif not is_serial:
                uniquestr += str(user_input[CONF_TCP_PORT])
            gateway_id = hashlib.sha256(uniquestr.encode()).hexdigest()[:8]
            await self.async_set_unique_id(gateway_id)
            self._abort_if_unique_id_configured()

            #if no errors so far, try to connect
            if not errors and not await try_connect(self.hass, user_input, uniqueid=gateway_id):
                errors["base"] = "cannot_connect"

            if not errors:
                _LOGGER.info("config_flow completed for %s", gateway_id)
                return self.async_create_entry(title=f"{user_input[CONF_DEVICE]}", data=user_input)

        schema = OrderedDict()
        schema[vol.Optional(CONF_OPTIMISTIC, default=False)] = bool
        schema[vol.Optional(CONF_PERSISTENCE, default=True)] = bool
        schema[vol.Optional(CONF_RETAIN, default=True)] = bool
        schema[vol.Optional(CONF_VERSION, default=DEFAULT_VERSION)] = str

        schema[vol.Required(CONF_DEVICE, default="127.0.0.1")] = str
        #schema[vol.Optional(CONF_PERSISTENCE_FILE)] = str
        schema[vol.Optional(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE)] = cv.positive_int
        schema[vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT)] = int
        schema[vol.Optional(CONF_TOPIC_IN_PREFIX)] = str
        schema[vol.Optional(CONF_TOPIC_OUT_PREFIX)] = str

        schema = vol.Schema(schema)
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )

