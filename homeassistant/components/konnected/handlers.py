"""Handle Konnected messages."""
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    CONF_STATE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import decorator

from .const import CONF_INVERSE, SIGNAL_DS18B20_NEW

_LOGGER = logging.getLogger(__name__)
HANDLERS = decorator.Registry()  # type: ignore[var-annotated]


@HANDLERS.register(CONF_STATE)
async def async_handle_state_update(hass, context, msg):
    """Handle a binary sensor or switch state update."""
    _LOGGER.debug("[state handler] context: %s  msg: %s", context, msg)
    entity_id = context.get(CONF_ENTITY_ID)
    state = bool(int(msg.get(ATTR_STATE)))
    if context.get(CONF_INVERSE):
        state = not state

    async_dispatcher_send(hass, f"konnected.{entity_id}.update", state)


@HANDLERS.register("temp")
async def async_handle_temp_update(hass, context, msg):
    """Handle a temperature sensor state update."""
    _LOGGER.debug("[temp handler] context: %s  msg: %s", context, msg)
    entity_id, temp = context.get(SensorDeviceClass.TEMPERATURE), msg.get("temp")
    if entity_id:
        async_dispatcher_send(hass, f"konnected.{entity_id}.update", temp)


@HANDLERS.register("humi")
async def async_handle_humi_update(hass, context, msg):
    """Handle a humidity sensor state update."""
    _LOGGER.debug("[humi handler] context: %s  msg: %s", context, msg)
    entity_id, humi = context.get(SensorDeviceClass.HUMIDITY), msg.get("humi")
    if entity_id:
        async_dispatcher_send(hass, f"konnected.{entity_id}.update", humi)


@HANDLERS.register("addr")
async def async_handle_addr_update(hass, context, msg):
    """Handle an addressable sensor update."""
    _LOGGER.debug("[addr handler] context: %s  msg: %s", context, msg)
    addr, temp = msg.get("addr"), msg.get("temp")
    if entity_id := context.get(addr):
        async_dispatcher_send(hass, f"konnected.{entity_id}.update", temp)
    else:
        msg[ATTR_DEVICE_ID] = context.get(ATTR_DEVICE_ID)
        msg[ATTR_TEMPERATURE] = temp
        msg["addr"] = addr
        async_dispatcher_send(hass, SIGNAL_DS18B20_NEW, msg)
