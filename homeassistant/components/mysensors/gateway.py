"""Handle MySensors gateways."""
from __future__ import annotations

import asyncio
from collections import defaultdict
import logging
import socket
import sys
from typing import Any, Callable, Coroutine

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
    MYSENSORS_GATEWAY_START_TASK,
    MYSENSORS_GATEWAYS,
    GatewayId,
)
from .handler import HANDLERS
from .helpers import (
    discover_mysensors_platform,
    on_unload,
    validate_child,
    validate_node,
)

_LOGGER = logging.getLogger(__name__)

GATEWAY_READY_TIMEOUT = 20.0
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


async def try_connect(hass: HomeAssistantType, user_input: dict[str, str]) -> bool:
    """Try to connect to a gateway and report if it worked."""
    if user_input[CONF_DEVICE] == MQTT_COMPONENT:
        return True  # dont validate mqtt. mqtt gateways dont send ready messages :(
    try:
        gateway_ready = asyncio.Event()

        def on_conn_made(_: BaseAsyncGateway) -> None:
            gateway_ready.set()

        gateway: BaseAsyncGateway | None = await _get_gateway(
            hass,
            device=user_input[CONF_DEVICE],
            version=user_input[CONF_VERSION],
            event_callback=lambda _: None,
            persistence_file=None,
            baud_rate=user_input.get(CONF_BAUD_RATE),
            tcp_port=user_input.get(CONF_TCP_PORT),
            topic_in_prefix=None,
            topic_out_prefix=None,
            retain=False,
            persistence=False,
        )
        if gateway is None:
            return False
        gateway.on_conn_made = on_conn_made

        connect_task = None
        try:
            connect_task = asyncio.create_task(gateway.start())
            with async_timeout.timeout(GATEWAY_READY_TIMEOUT):
                await gateway_ready.wait()
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


def get_mysensors_gateway(
    hass: HomeAssistantType, gateway_id: GatewayId
) -> BaseAsyncGateway | None:
    """Return the Gateway for a given GatewayId."""
    if MYSENSORS_GATEWAYS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][MYSENSORS_GATEWAYS] = {}
    gateways = hass.data[DOMAIN].get(MYSENSORS_GATEWAYS)
    return gateways.get(gateway_id)


async def setup_gateway(
    hass: HomeAssistantType, entry: ConfigEntry
) -> BaseAsyncGateway | None:
    """Set up the Gateway for the given ConfigEntry."""

    ready_gateway = await _get_gateway(
        hass,
        device=entry.data[CONF_DEVICE],
        version=entry.data[CONF_VERSION],
        event_callback=_gw_callback_factory(hass, entry.entry_id),
        persistence_file=entry.data.get(
            CONF_PERSISTENCE_FILE, f"mysensors_{entry.entry_id}.json"
        ),
        baud_rate=entry.data.get(CONF_BAUD_RATE),
        tcp_port=entry.data.get(CONF_TCP_PORT),
        topic_in_prefix=entry.data.get(CONF_TOPIC_IN_PREFIX),
        topic_out_prefix=entry.data.get(CONF_TOPIC_OUT_PREFIX),
        retain=entry.data.get(CONF_RETAIN, False),
    )
    return ready_gateway


async def _get_gateway(
    hass: HomeAssistantType,
    device: str,
    version: str,
    event_callback: Callable[[Message], None],
    persistence_file: str | None = None,
    baud_rate: int | None = None,
    tcp_port: int | None = None,
    topic_in_prefix: str | None = None,
    topic_out_prefix: str | None = None,
    retain: bool = False,
    persistence: bool = True,  # old persistence option has been deprecated. kwarg is here so we can run try_connect() without persistence
) -> BaseAsyncGateway | None:
    """Return gateway after setup of the gateway."""

    if persistence_file is not None:
        # interpret relative paths to be in hass config folder. absolute paths will be left as they are
        persistence_file = hass.config.path(persistence_file)

    if device == MQTT_COMPONENT:
        # what is the purpose of this?
        # if not await async_setup_component(hass, MQTT_COMPONENT, entry):
        #    return None
        mqtt = hass.components.mqtt

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
            in_prefix=topic_in_prefix,
            out_prefix=topic_out_prefix,
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
                _LOGGER.error("Connect failed: Invalid device %s", device)
                return None
    gateway.event_callback = event_callback
    if persistence:
        await gateway.start_persistence()

    return gateway


async def finish_setup(
    hass: HomeAssistantType, entry: ConfigEntry, gateway: BaseAsyncGateway
):
    """Load any persistent devices and platforms and start gateway."""
    discover_tasks = []
    start_tasks = []
    discover_tasks.append(_discover_persistent_devices(hass, entry, gateway))
    start_tasks.append(_gw_start(hass, entry, gateway))
    if discover_tasks:
        # Make sure all devices and platforms are loaded before gateway start.
        await asyncio.wait(discover_tasks)
    if start_tasks:
        await asyncio.wait(start_tasks)


async def _discover_persistent_devices(
    hass: HomeAssistantType, entry: ConfigEntry, gateway: BaseAsyncGateway
):
    """Discover platforms for devices loaded via persistence file."""
    tasks = []
    new_devices = defaultdict(list)
    for node_id in gateway.sensors:
        if not validate_node(gateway, node_id):
            continue
        node: Sensor = gateway.sensors[node_id]
        for child in node.children.values():  # child is of type ChildSensor
            validated = validate_child(entry.entry_id, gateway, node_id, child)
            for platform, dev_ids in validated.items():
                new_devices[platform].extend(dev_ids)
    _LOGGER.debug("discovering persistent devices: %s", new_devices)
    for platform, dev_ids in new_devices.items():
        discover_mysensors_platform(hass, entry.entry_id, platform, dev_ids)
    if tasks:
        await asyncio.wait(tasks)


async def gw_stop(hass, entry: ConfigEntry, gateway: BaseAsyncGateway):
    """Stop the gateway."""
    connect_task = hass.data[DOMAIN].pop(
        MYSENSORS_GATEWAY_START_TASK.format(entry.entry_id), None
    )
    if connect_task is not None and not connect_task.done():
        connect_task.cancel()
    await gateway.stop()


async def _gw_start(
    hass: HomeAssistantType, entry: ConfigEntry, gateway: BaseAsyncGateway
):
    """Start the gateway."""
    gateway_ready = asyncio.Event()

    def gateway_connected(_: BaseAsyncGateway):
        gateway_ready.set()

    gateway.on_conn_made = gateway_connected
    # Don't use hass.async_create_task to avoid holding up setup indefinitely.
    hass.data[DOMAIN][
        MYSENSORS_GATEWAY_START_TASK.format(entry.entry_id)
    ] = asyncio.create_task(
        gateway.start()
    )  # store the connect task so it can be cancelled in gw_stop

    async def stop_this_gw(_: Event):
        await gw_stop(hass, entry, gateway)

    await on_unload(
        hass,
        entry.entry_id,
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_this_gw),
    )

    if entry.data[CONF_DEVICE] == MQTT_COMPONENT:
        # Gatways connected via mqtt doesn't send gateway ready message.
        return
    try:
        with async_timeout.timeout(GATEWAY_READY_TIMEOUT):
            await gateway_ready.wait()
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Gateway %s not connected after %s secs so continuing with setup",
            entry.data[CONF_DEVICE],
            GATEWAY_READY_TIMEOUT,
        )


def _gw_callback_factory(
    hass: HomeAssistantType, gateway_id: GatewayId
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
            [Any, GatewayId, Message], Coroutine[None]
        ] = HANDLERS.get(msg_type.name)

        if msg_handler is None:
            return

        hass.async_create_task(msg_handler(hass, gateway_id, msg))

    return mysensors_callback
