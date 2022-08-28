"""Handle MySensors gateways."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
import logging
import socket
import sys
from typing import Any

import async_timeout
from mysensors import BaseAsyncGateway, Message, Sensor, mysensors
import voluptuous as vol

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mqtt.models import (
    ReceiveMessage as MQTTReceiveMessage,
    ReceivePayloadType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_MQTT,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_PERSISTENCE_FILE,
    CONF_RETAIN,
    CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX,
    CONF_TOPIC_OUT_PREFIX,
    CONF_VERSION,
    DOMAIN,
    MYSENSORS_GATEWAY_START_TASK,
    ConfGatewayType,
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


def is_serial_port(value: str) -> str:
    """Validate that value is a windows serial port or a unix device."""
    if sys.platform.startswith("win"):
        ports = (f"COM{idx + 1}" for idx in range(256))
        if value in ports:
            return value
        raise vol.Invalid(f"{value} is not a serial port")
    return cv.isdevice(value)


def is_socket_address(value: str) -> str:
    """Validate that value is a valid address."""
    try:
        socket.getaddrinfo(value, None)
        return value
    except OSError as err:
        raise vol.Invalid("Device is not a valid domain name or ip address") from err


async def try_connect(
    hass: HomeAssistant, gateway_type: ConfGatewayType, user_input: dict[str, Any]
) -> bool:
    """Try to connect to a gateway and report if it worked."""
    if gateway_type == "MQTT":
        return True  # Do not validate MQTT, as that does not use connection made.
    try:
        gateway_ready = asyncio.Event()

        def on_conn_made(_: BaseAsyncGateway) -> None:
            gateway_ready.set()

        gateway: BaseAsyncGateway | None = await _get_gateway(
            hass,
            gateway_type,
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
            async with async_timeout.timeout(GATEWAY_READY_TIMEOUT):
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


async def setup_gateway(
    hass: HomeAssistant, entry: ConfigEntry
) -> BaseAsyncGateway | None:
    """Set up the Gateway for the given ConfigEntry."""

    ready_gateway = await _get_gateway(
        hass,
        gateway_type=entry.data[CONF_GATEWAY_TYPE],
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
    hass: HomeAssistant,
    gateway_type: ConfGatewayType,
    device: str,
    version: str,
    event_callback: Callable[[Message], None],
    persistence_file: str | None = None,
    baud_rate: int | None = None,
    tcp_port: int | None = None,
    topic_in_prefix: str | None = None,
    topic_out_prefix: str | None = None,
    retain: bool = False,
    persistence: bool = True,
) -> BaseAsyncGateway | None:
    """Return gateway after setup of the gateway."""

    if persistence_file is not None:
        # Interpret relative paths to be in hass config folder.
        # Absolute paths will be left as they are.
        persistence_file = hass.config.path(persistence_file)

    if gateway_type == CONF_GATEWAY_TYPE_MQTT:
        # Make sure the mqtt integration is set up.
        # Naive check that doesn't consider config entry state.
        if MQTT_DOMAIN not in hass.config.components:
            return None
        mqtt = hass.components.mqtt

        def pub_callback(topic: str, payload: str, qos: int, retain: bool) -> None:
            """Call MQTT publish function."""
            hass.async_create_task(
                mqtt.async_publish(hass, topic, payload, qos, retain)
            )

        def sub_callback(
            topic: str, sub_cb: Callable[[str, ReceivePayloadType, int], None], qos: int
        ) -> None:
            """Call MQTT subscribe function."""

            @callback
            def internal_callback(msg: MQTTReceiveMessage) -> None:
                """Call callback."""
                sub_cb(msg.topic, msg.payload, msg.qos)

            hass.async_create_task(mqtt.async_subscribe(topic, internal_callback, qos))

        gateway = mysensors.AsyncMQTTGateway(
            pub_callback,
            sub_callback,
            in_prefix=topic_in_prefix,
            out_prefix=topic_out_prefix,
            retain=retain,
            event_callback=None,
            persistence=persistence,
            persistence_file=persistence_file,
            protocol_version=version,
        )
    elif gateway_type == CONF_GATEWAY_TYPE_SERIAL:
        gateway = mysensors.AsyncSerialGateway(
            device,
            baud=baud_rate,
            event_callback=None,
            persistence=persistence,
            persistence_file=persistence_file,
            protocol_version=version,
        )
    else:
        gateway = mysensors.AsyncTCPGateway(
            device,
            port=tcp_port,
            event_callback=None,
            persistence=persistence,
            persistence_file=persistence_file,
            protocol_version=version,
        )
    gateway.event_callback = event_callback
    gateway.metric = hass.config.units.is_metric

    if persistence:
        await gateway.start_persistence()

    return gateway


async def finish_setup(
    hass: HomeAssistant, entry: ConfigEntry, gateway: BaseAsyncGateway
) -> None:
    """Load any persistent devices and platforms and start gateway."""
    await _discover_persistent_devices(hass, entry, gateway)
    await _gw_start(hass, entry, gateway)


async def _discover_persistent_devices(
    hass: HomeAssistant, entry: ConfigEntry, gateway: BaseAsyncGateway
) -> None:
    """Discover platforms for devices loaded via persistence file."""
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


async def gw_stop(
    hass: HomeAssistant, entry: ConfigEntry, gateway: BaseAsyncGateway
) -> None:
    """Stop the gateway."""
    connect_task = hass.data[DOMAIN].pop(
        MYSENSORS_GATEWAY_START_TASK.format(entry.entry_id), None
    )
    if connect_task is not None and not connect_task.done():
        connect_task.cancel()
    await gateway.stop()


async def _gw_start(
    hass: HomeAssistant, entry: ConfigEntry, gateway: BaseAsyncGateway
) -> None:
    """Start the gateway."""
    gateway_ready = asyncio.Event()

    def gateway_connected(_: BaseAsyncGateway) -> None:
        """Handle gateway connected."""
        gateway_ready.set()

    gateway.on_conn_made = gateway_connected
    # Don't use hass.async_create_task to avoid holding up setup indefinitely.
    hass.data[DOMAIN][
        MYSENSORS_GATEWAY_START_TASK.format(entry.entry_id)
    ] = asyncio.create_task(
        gateway.start()
    )  # store the connect task so it can be cancelled in gw_stop

    async def stop_this_gw(_: Event) -> None:
        """Stop the gateway."""
        await gw_stop(hass, entry, gateway)

    on_unload(
        hass,
        entry.entry_id,
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_this_gw),
    )

    if entry.data[CONF_DEVICE] == MQTT_COMPONENT:
        # Gatways connected via mqtt doesn't send gateway ready message.
        return
    try:
        async with async_timeout.timeout(GATEWAY_READY_TIMEOUT):
            await gateway_ready.wait()
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Gateway %s not connected after %s secs so continuing with setup",
            entry.data[CONF_DEVICE],
            GATEWAY_READY_TIMEOUT,
        )


def _gw_callback_factory(
    hass: HomeAssistant, gateway_id: GatewayId
) -> Callable[[Message], None]:
    """Return a new callback for the gateway."""

    @callback
    def mysensors_callback(msg: Message) -> None:
        """Handle messages from a MySensors gateway.

        All MySenors messages are received here.
        The messages are passed to handler functions depending on their type.
        """
        _LOGGER.debug("Node update: node %s child %s", msg.node_id, msg.child_id)

        msg_type = msg.gateway.const.MessageType(msg.type)
        msg_handler = HANDLERS.get(msg_type.name)

        if msg_handler is None:
            return

        hass.async_create_task(msg_handler(hass, gateway_id, msg))

    return mysensors_callback
