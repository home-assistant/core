"""Handle MySensors gateways."""
import asyncio
from collections import defaultdict
import logging
import socket
import sys
from typing import Any, Callable, Coroutine, Dict, Optional, Union

import async_timeout
from mysensors import BaseAsyncGateway, Message, Sensor, mysensors
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    MYSENSORS_GATEWAY_READY,
    MYSENSORS_GATEWAY_START_TASK,
    MYSENSORS_GATEWAYS,
    GatewayId,
)
from .handler import HANDLERS
from .helpers import discover_mysensors_platform, validate_child, validate_node

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


def get_mysensors_gateway(
    hass: HomeAssistantType, gateway_id: GatewayId
) -> Optional[BaseAsyncGateway]:
    """Return the Gateway for a given GatewayId."""
    if MYSENSORS_GATEWAYS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][MYSENSORS_GATEWAYS] = {}
    gateways = hass.data[DOMAIN].get(MYSENSORS_GATEWAYS)
    return gateways.get(gateway_id)


async def setup_gateway(
    hass: HomeAssistantType, entry: ConfigEntry
) -> Optional[BaseAsyncGateway]:
    """Set up all gateways."""

    ready_gateway = await _get_gateway(hass, entry)
    return ready_gateway


async def _get_gateway(
    hass: HomeAssistantType,
    entry: Union[ConfigEntry, Dict[str, Any]],
    unique_id: Optional[str] = None,
    persistence: bool = True,  # old persistence option has been deprecated. kwarg is here so we can run try_connect() without persistence
) -> Optional[BaseAsyncGateway]:
    """Return gateway after setup of the gateway."""

    if isinstance(entry, ConfigEntry):
        data: Dict[str, Any] = entry.data
        unique_id = entry.entry_id
    else:
        data: Dict[str, Any] = entry

    if unique_id is None:
        raise ValueError(
            "no unique id! either give configEntry for auto-extraction or explicitly give one"
        )
    persistence_file = data.get(
        CONF_PERSISTENCE_FILE, hass.config.path(f"mysensors_{unique_id}.pickle")
    )
    version = data.get(CONF_VERSION)
    device = data.get(CONF_DEVICE)
    baud_rate = data.get(CONF_BAUD_RATE)
    tcp_port = data.get(CONF_TCP_PORT)
    in_prefix = data.get(CONF_TOPIC_IN_PREFIX, "")
    out_prefix = data.get(CONF_TOPIC_OUT_PREFIX, "")

    if device == MQTT_COMPONENT:
        # what is the purpose of this?
        # if not await async_setup_component(hass, MQTT_COMPONENT, entry):
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
    gateway.optimistic = False  # old optimistic option has been deprecated, we use echos to hopefully not need it
    gateway.device = device
    gateway.entry_id = unique_id
    gateway.event_callback = _gw_callback_factory(hass, entry)
    if persistence:
        await gateway.start_persistence()

    return gateway


async def finish_setup(
    hass: HomeAssistantType, hass_config: ConfigEntry, gateway: BaseAsyncGateway
):
    """Load any persistent devices and platforms and start gateway."""
    discover_tasks = []
    start_tasks = []
    discover_tasks.append(_discover_persistent_devices(hass, hass_config, gateway))
    start_tasks.append(_gw_start(hass, gateway))
    if discover_tasks:
        # Make sure all devices and platforms are loaded before gateway start.
        await asyncio.wait(discover_tasks)
    if start_tasks:
        await asyncio.wait(start_tasks)


async def _discover_persistent_devices(
    hass: HomeAssistantType, hass_config: ConfigEntry, gateway: BaseAsyncGateway
):
    """Discover platforms for devices loaded via persistence file."""
    tasks = []
    new_devices = defaultdict(list)
    for node_id in gateway.sensors:
        if not validate_node(gateway, node_id):
            continue
        node: Sensor = gateway.sensors[node_id]
        for child in node.children.values():  # child is of type ChildSensor
            validated = validate_child(gateway, node_id, child)
            for platform, dev_ids in validated.items():
                new_devices[platform].extend(dev_ids)
    _LOGGER.debug("discovering persistent devices: %s", new_devices)
    for platform, dev_ids in new_devices.items():
        discover_mysensors_platform(hass, hass_config, platform, dev_ids)
    if tasks:
        await asyncio.wait(tasks)


async def gw_stop(hass, gateway: BaseAsyncGateway):
    """Stop the gateway."""
    _LOGGER.info("stopping gateway %s", gateway.entry_id)
    connect_task = hass.data[DOMAIN].get(
        MYSENSORS_GATEWAY_START_TASK.format(gateway.entry_id), None
    )
    if connect_task is not None and not connect_task.done():
        connect_task.cancel()
    await gateway.stop()


async def _gw_start(hass: HomeAssistantType, gateway: BaseAsyncGateway):
    """Start the gateway."""
    # Don't use hass.async_create_task to avoid holding up setup indefinitely.
    hass.data[DOMAIN][
        MYSENSORS_GATEWAY_START_TASK.format(gateway.entry_id)
    ] = asyncio.create_task(
        gateway.start()
    )  # store the connect task so it can be cancelled in gw_stop

    async def stop_this_gw(_: Event):
        await gw_stop(hass, gateway)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_this_gw)
    if gateway.device == "mqtt":
        # Gatways connected via mqtt doesn't send gateway ready message.
        return
    gateway_ready = asyncio.Future()
    gateway_ready_key = MYSENSORS_GATEWAY_READY.format(gateway.entry_id)
    hass.data[DOMAIN][gateway_ready_key] = gateway_ready

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
        hass.data[DOMAIN].pop(gateway_ready_key, None)


def _gw_callback_factory(
    hass: HomeAssistantType, hass_config: ConfigEntry
) -> Callable[[Message], None]:
    """Return a new callback for the gateway."""

    @callback
    def mysensors_callback(msg: Message):
        """Handle messages from a MySensors gateway.

        All MySenors messages are received here.
        The messages are passed to handler functions depending on their type.
        """
        _LOGGER.debug("Node update: node %s child %s", msg.node_id, msg.child_id)

        msg_type = msg.gateway.const.MessageType(msg.type)
        msg_handler: Callable[
            [Any, ConfigEntry, Message], Coroutine[None]
        ] = HANDLERS.get(msg_type.name)

        if msg_handler is None:
            return

        hass.async_create_task(msg_handler(hass, hass_config, msg))

    return mysensors_callback
