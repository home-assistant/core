"""Handle MySensors gateways."""
import asyncio
from collections import defaultdict
import logging
import socket
import sys

import async_timeout
from mysensors import mysensors, BaseAsyncGateway, Sensor, Message
from typing import Optional, List, Any, Callable, Coroutine
import voluptuous as vol

from homeassistant.const import CONF_OPTIMISTIC, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.setup import async_setup_component

from .const import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAYS,
    CONF_NODES,
    CONF_PERSISTENCE,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    MYSENSORS_GATEWAY_READY,
    MYSENSORS_GATEWAYS,
)
from .const import GatewayId
from .handler import HANDLERS
from .helpers import discover_mysensors_platform, validate_child, validate_node
from ...config_entries import ConfigEntry
from ...helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

GATEWAY_READY_TIMEOUT = 15.0
MQTT_COMPONENT = "mqtt"


def is_serial_port(value):
    """Validate that value is a windows serial port or a unix device."""
    if sys.platform.startswith("win"):
        ports = (f"COM{idx + 1}" for idx in range(256))
        if value in ports:
            return value
        raise vol.Invalid(f"{value} is not a serial port")
    return cv.isdevice(value)


def is_socket_address(value):
    """Validate that value is a valid address."""
    try:
        socket.getaddrinfo(value, None)
        return value
    except OSError as err:
        raise vol.Invalid("Device is not a valid domain name or ip address") from err


def get_mysensors_gateway(hass: HomeAssistantType, gateway_id: GatewayId) -> Optional[BaseAsyncGateway]:
    """Returns the Gateway for a given GatewayId."""
    if MYSENSORS_GATEWAYS not in hass.data:
        hass.data[MYSENSORS_GATEWAYS] = {}
    gateways = hass.data.get(MYSENSORS_GATEWAYS)
    return gateways.get(gateway_id)


async def setup_gateways(hass: HomeAssistantType, config):
    """Set up all gateways."""
    conf = config[DOMAIN]
    gateways = {}

    for index, gateway_conf in enumerate(conf[CONF_GATEWAYS]):
        persistence_file = gateway_conf.get(
            CONF_PERSISTENCE_FILE,
            hass.config.path(f"mysensors{index + 1}.pickle"),
        )
        ready_gateway = await _get_gateway(hass, config, gateway_conf, persistence_file)
        if ready_gateway is not None:
            gateways[id(ready_gateway)] = ready_gateway

    return gateways


async def _get_gateway(hass: HomeAssistantType, entry: Union[ConfigEntry,Dict[str, Any]], unique_id: Optional[str]=None) -> Optional[BaseAsyncGateway]:
    """Return gateway after setup of the gateway."""

    if isinstance(entry, ConfigEntry):
        data: Dict[str, Any] = entry.data
        unique_id = entry.unique_id
    else:
        data: Dict[str, Any] = entry

    if unique_id is None:
        raise ValueError("no unique id! either give configEntry for auto-extraction or explicitly give one")
    persistence_file = data.get(CONF_PERSISTENCE_FILE, hass.config.path(f"mysensors{unique_id}.pickle"))
    persistence = data.get(CONF_PERSISTENCE)
    version = data.get(CONF_VERSION)
    device = data.get(CONF_DEVICE)
    baud_rate = data.get(CONF_BAUD_RATE)
    tcp_port = data.get(CONF_TCP_PORT)
    in_prefix = data.get(CONF_TOPIC_IN_PREFIX, "")
    out_prefix = data.get(CONF_TOPIC_OUT_PREFIX, "")

    if device == MQTT_COMPONENT:
        #what is the purpose of this?
        #if not await async_setup_component(hass, MQTT_COMPONENT, entry):
        #    return None
        mqtt = hass.components.mqtt
        retain = data.get(CONF_RETAIN)

        def pub_callback(topic, payload, qos, retain):
            """Call MQTT publish function."""
            mqtt.async_publish(topic, payload, qos, retain)

        def sub_callback(topic, sub_cb, qos):
            """Call MQTT subscribe function."""

            @callback
            def internal_callback(msg):
                """Call callback."""
                sub_cb(msg.topic, msg.payload, msg.qos)

            hass.async_create_task(mqtt.async_subscribe(topic, internal_callback, qos))

        gateway = mysensors.AsyncMQTTGateway(
            pub_callback,
            sub_callback,
            in_prefix=in_prefix,
            out_prefix=out_prefix,
            retain=retain,
            loop=hass.loop,
            event_callback=None,
            persistence=persistence,
            persistence_file=persistence_file,
            protocol_version=version,
        )
    else:
        try:
            await hass.async_add_executor_job(is_serial_port, device)
            gateway = mysensors.AsyncSerialGateway(
                device,
                baud=baud_rate,
                loop=hass.loop,
                event_callback=None,
                persistence=persistence,
                persistence_file=persistence_file,
                protocol_version=version,
            )
        except vol.Invalid:
            try:
                await hass.async_add_executor_job(is_socket_address, device)
                # valid ip address
                gateway = mysensors.AsyncTCPGateway(
                    device,
                    port=tcp_port,
                    loop=hass.loop,
                    event_callback=None,
                    persistence=persistence,
                    persistence_file=persistence_file,
                    protocol_version=version,
                )
            except vol.Invalid:
                # invalid ip address
                return None
    # this adds extra properties to the pymysensors objects
    gateway.metric = hass.config.units.is_metric
    gateway.optimistic = data.get(CONF_OPTIMISTIC)
    gateway.device = device
    gateway.unique_id = unique_id
    gateway.event_callback = _gw_callback_factory(hass, entry)
    if persistence:
        await gateway.start_persistence()

    return gateway


async def finish_setup(hass: HomeAssistantType, hass_config, gateways: List[BaseAsyncGateway]):
    """Load any persistent devices and platforms and start gateway."""
    discover_tasks = []
    start_tasks = []
    for gateway in gateways.values():
        discover_tasks.append(_discover_persistent_devices(hass, hass_config, gateway))
        start_tasks.append(_gw_start(hass, gateway))
    if discover_tasks:
        # Make sure all devices and platforms are loaded before gateway start.
        await asyncio.wait(discover_tasks)
    if start_tasks:
        await asyncio.wait(start_tasks)


async def _discover_persistent_devices(hass: HomeAssistantType, hass_config, gateway: BaseAsyncGateway):
    """Discover platforms for devices loaded via persistence file."""
    tasks = []
    new_devices = defaultdict(list)
    for node_id in gateway.sensors:
        if not validate_node(gateway, node_id):
            continue
        node: Sensor = gateway.sensors[node_id]
        for child in node.children.values():#child is of type ChildSensor
            validated = validate_child(gateway, node_id, child)
            for platform, dev_ids in validated.items():
                new_devices[platform].extend(dev_ids)
    for platform, dev_ids in new_devices.items():
        tasks.append(discover_mysensors_platform(hass, hass_config, platform, dev_ids))
    if tasks:
        await asyncio.wait(tasks)


async def _gw_start(hass: HomeAssistantType, gateway: BaseAsyncGateway):
    """Start the gateway."""
    # Don't use hass.async_create_task to avoid holding up setup indefinitely.
    connect_task = hass.loop.create_task(gateway.start())

    @callback
    def gw_stop(event):
        """Trigger to stop the gateway."""
        hass.async_create_task(gateway.stop())
        if not connect_task.done():
            connect_task.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gw_stop)
    if gateway.device == "mqtt":
        # Gatways connected via mqtt doesn't send gateway ready message.
        return
    gateway_ready = asyncio.Future()
    gateway_ready_key = MYSENSORS_GATEWAY_READY.format(gateway.unique_id)
    hass.data[gateway_ready_key] = gateway_ready

    try:
        with async_timeout.timeout(GATEWAY_READY_TIMEOUT):
            await gateway_ready
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Gateway %s not ready after %s secs so continuing with setup",
            gateway.device,
            GATEWAY_READY_TIMEOUT,
        )
    finally:
        hass.data.pop(gateway_ready_key, None)


def _gw_callback_factory(hass: HomeAssistantType, hass_config) -> Callable[[Message], None]:
    """Return a new callback for the gateway."""

    @callback
    def mysensors_callback(msg: Message):
        """Handle messages from a MySensors gateway."""
        _LOGGER.debug("Node update: node %s child %s", msg.node_id, msg.child_id)

        msg_type = msg.gateway.const.MessageType(msg.type)
        msg_handler: Callable[[Any, ConfigEntry, Message], Coroutine[None]] = HANDLERS.get(
            msg_type.name
        )

        if msg_handler is None:
            return

        hass.async_create_task(msg_handler(hass, hass_config, msg))

    return mysensors_callback
