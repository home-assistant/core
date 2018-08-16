"""Handle MySensors gateways."""
import asyncio
from collections import defaultdict
import logging
import socket
import sys
from timeit import default_timer as timer

import async_timeout
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from .const import (
    ATTR_DEVICES, CONF_BAUD_RATE, CONF_DEVICE, CONF_GATEWAYS, CONF_NODES,
    CONF_PERSISTENCE, CONF_PERSISTENCE_FILE, CONF_RETAIN, CONF_TCP_PORT,
    CONF_TOPIC_IN_PREFIX, CONF_TOPIC_OUT_PREFIX, CONF_VERSION, DOMAIN,
    MYSENSORS_CONST_SCHEMA, MYSENSORS_GATEWAYS, PLATFORM, SCHEMA,
    SIGNAL_CALLBACK, TYPE)
from .device import get_mysensors_devices

_LOGGER = logging.getLogger(__name__)

GATEWAY_READY_TIMEOUT = 15.0
MQTT_COMPONENT = 'mqtt'
MYSENSORS_GATEWAY_READY = 'mysensors_gateway_ready_{}'


def is_serial_port(value):
    """Validate that value is a windows serial port or a unix device."""
    if sys.platform.startswith('win'):
        ports = ('COM{}'.format(idx + 1) for idx in range(256))
        if value in ports:
            return value
        raise vol.Invalid('{} is not a serial port'.format(value))
    return cv.isdevice(value)


def is_socket_address(value):
    """Validate that value is a valid address."""
    try:
        socket.getaddrinfo(value, None)
        return value
    except OSError:
        raise vol.Invalid('Device is not a valid domain name or ip address')


def get_mysensors_gateway(hass, gateway_id):
    """Return MySensors gateway."""
    if MYSENSORS_GATEWAYS not in hass.data:
        hass.data[MYSENSORS_GATEWAYS] = {}
    gateways = hass.data.get(MYSENSORS_GATEWAYS)
    return gateways.get(gateway_id)


async def setup_gateways(hass, config):
    """Set up all gateways."""
    conf = config[DOMAIN]
    gateways = {}

    for index, gateway_conf in enumerate(conf[CONF_GATEWAYS]):
        persistence_file = gateway_conf.get(
            CONF_PERSISTENCE_FILE,
            hass.config.path('mysensors{}.pickle'.format(index + 1)))
        ready_gateway = await _get_gateway(
            hass, config, gateway_conf, persistence_file)
        if ready_gateway is not None:
            gateways[id(ready_gateway)] = ready_gateway

    return gateways


async def _get_gateway(hass, config, gateway_conf, persistence_file):
    """Return gateway after setup of the gateway."""
    from mysensors import mysensors

    conf = config[DOMAIN]
    persistence = conf[CONF_PERSISTENCE]
    version = conf[CONF_VERSION]
    device = gateway_conf[CONF_DEVICE]
    baud_rate = gateway_conf[CONF_BAUD_RATE]
    tcp_port = gateway_conf[CONF_TCP_PORT]
    in_prefix = gateway_conf.get(CONF_TOPIC_IN_PREFIX, '')
    out_prefix = gateway_conf.get(CONF_TOPIC_OUT_PREFIX, '')

    if device == MQTT_COMPONENT:
        if not await async_setup_component(hass, MQTT_COMPONENT, config):
            return None
        mqtt = hass.components.mqtt
        retain = conf[CONF_RETAIN]

        def pub_callback(topic, payload, qos, retain):
            """Call MQTT publish function."""
            mqtt.async_publish(topic, payload, qos, retain)

        def sub_callback(topic, sub_cb, qos):
            """Call MQTT subscribe function."""
            @callback
            def internal_callback(*args):
                """Call callback."""
                sub_cb(*args)

            hass.async_add_job(
                mqtt.async_subscribe(topic, internal_callback, qos))

        gateway = mysensors.AsyncMQTTGateway(
            pub_callback, sub_callback, in_prefix=in_prefix,
            out_prefix=out_prefix, retain=retain, loop=hass.loop,
            event_callback=None, persistence=persistence,
            persistence_file=persistence_file,
            protocol_version=version)
    else:
        try:
            await hass.async_add_job(is_serial_port, device)
            gateway = mysensors.AsyncSerialGateway(
                device, baud=baud_rate, loop=hass.loop,
                event_callback=None, persistence=persistence,
                persistence_file=persistence_file,
                protocol_version=version)
        except vol.Invalid:
            try:
                await hass.async_add_job(is_socket_address, device)
                # valid ip address
                gateway = mysensors.AsyncTCPGateway(
                    device, port=tcp_port, loop=hass.loop, event_callback=None,
                    persistence=persistence, persistence_file=persistence_file,
                    protocol_version=version)
            except vol.Invalid:
                # invalid ip address
                return None
    gateway.metric = hass.config.units.is_metric
    gateway.optimistic = conf[CONF_OPTIMISTIC]
    gateway.device = device
    gateway.event_callback = _gw_callback_factory(hass)
    gateway.nodes_config = gateway_conf[CONF_NODES]
    if persistence:
        await gateway.start_persistence()

    return gateway


async def finish_setup(hass, gateways):
    """Load any persistent devices and platforms and start gateway."""
    discover_tasks = []
    start_tasks = []
    for gateway in gateways.values():
        discover_tasks.append(_discover_persistent_devices(hass, gateway))
        start_tasks.append(_gw_start(hass, gateway))
    if discover_tasks:
        # Make sure all devices and platforms are loaded before gateway start.
        await asyncio.wait(discover_tasks, loop=hass.loop)
    if start_tasks:
        await asyncio.wait(start_tasks, loop=hass.loop)


async def _discover_persistent_devices(hass, gateway):
    """Discover platforms for devices loaded via persistence file."""
    tasks = []
    new_devices = defaultdict(list)
    for node_id in gateway.sensors:
        node = gateway.sensors[node_id]
        for child in node.children.values():
            validated = _validate_child(gateway, node_id, child)
            for platform, dev_ids in validated.items():
                new_devices[platform].extend(dev_ids)
    for platform, dev_ids in new_devices.items():
        tasks.append(_discover_mysensors_platform(hass, platform, dev_ids))
    if tasks:
        await asyncio.wait(tasks, loop=hass.loop)


@callback
def _discover_mysensors_platform(hass, platform, new_devices):
    """Discover a MySensors platform."""
    task = hass.async_create_task(discovery.async_load_platform(
        hass, platform, DOMAIN,
        {ATTR_DEVICES: new_devices, CONF_NAME: DOMAIN}))
    return task


async def _gw_start(hass, gateway):
    """Start the gateway."""
    # Don't use hass.async_create_task to avoid holding up setup indefinitely.
    connect_task = hass.loop.create_task(gateway.start())

    @callback
    def gw_stop(event):
        """Trigger to stop the gateway."""
        hass.async_add_job(gateway.stop())
        if not connect_task.done():
            connect_task.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, gw_stop)
    if gateway.device == 'mqtt':
        # Gatways connected via mqtt doesn't send gateway ready message.
        return
    gateway_ready = asyncio.Future()
    gateway_ready_key = MYSENSORS_GATEWAY_READY.format(id(gateway))
    hass.data[gateway_ready_key] = gateway_ready

    try:
        with async_timeout.timeout(GATEWAY_READY_TIMEOUT, loop=hass.loop):
            await gateway_ready
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Gateway %s not ready after %s secs so continuing with setup",
            gateway.device, GATEWAY_READY_TIMEOUT)
    finally:
        hass.data.pop(gateway_ready_key, None)


def _gw_callback_factory(hass):
    """Return a new callback for the gateway."""
    @callback
    def mysensors_callback(msg):
        """Handle messages from a MySensors gateway."""
        start = timer()
        _LOGGER.debug(
            "Node update: node %s child %s", msg.node_id, msg.child_id)

        _set_gateway_ready(hass, msg)

        try:
            child = msg.gateway.sensors[msg.node_id].children[msg.child_id]
        except KeyError:
            _LOGGER.debug("Not a child update for node %s", msg.node_id)
            return

        signals = []

        # Update all platforms for the device via dispatcher.
        # Add/update entity if schema validates to true.
        validated = _validate_child(msg.gateway, msg.node_id, child)
        for platform, dev_ids in validated.items():
            devices = get_mysensors_devices(hass, platform)
            new_dev_ids = []
            for dev_id in dev_ids:
                if dev_id in devices:
                    signals.append(SIGNAL_CALLBACK.format(*dev_id))
                else:
                    new_dev_ids.append(dev_id)
            if new_dev_ids:
                _discover_mysensors_platform(hass, platform, new_dev_ids)
        for signal in set(signals):
            # Only one signal per device is needed.
            # A device can have multiple platforms, ie multiple schemas.
            # FOR LATER: Add timer to not signal if another update comes in.
            async_dispatcher_send(hass, signal)
        end = timer()
        if end - start > 0.1:
            _LOGGER.debug(
                "Callback for node %s child %s took %.3f seconds",
                msg.node_id, msg.child_id, end - start)
    return mysensors_callback


@callback
def _set_gateway_ready(hass, msg):
    """Set asyncio future result if gateway is ready."""
    if (msg.type != msg.gateway.const.MessageType.internal or
            msg.sub_type != msg.gateway.const.Internal.I_GATEWAY_READY):
        return
    gateway_ready = hass.data.get(MYSENSORS_GATEWAY_READY.format(
        id(msg.gateway)))
    if gateway_ready is None or gateway_ready.cancelled():
        return
    gateway_ready.set_result(True)


def _validate_child(gateway, node_id, child):
    """Validate that a child has the correct values according to schema.

    Return a dict of platform with a list of device ids for validated devices.
    """
    validated = defaultdict(list)

    if not child.values:
        _LOGGER.debug(
            "No child values for node %s child %s", node_id, child.id)
        return validated
    if gateway.sensors[node_id].sketch_name is None:
        _LOGGER.debug("Node %s is missing sketch name", node_id)
        return validated
    pres = gateway.const.Presentation
    set_req = gateway.const.SetReq
    s_name = next(
        (member.name for member in pres if member.value == child.type), None)
    if s_name not in MYSENSORS_CONST_SCHEMA:
        _LOGGER.warning("Child type %s is not supported", s_name)
        return validated
    child_schemas = MYSENSORS_CONST_SCHEMA[s_name]

    def msg(name):
        """Return a message for an invalid schema."""
        return "{} requires value_type {}".format(
            pres(child.type).name, set_req[name].name)

    for schema in child_schemas:
        platform = schema[PLATFORM]
        v_name = schema[TYPE]
        value_type = next(
            (member.value for member in set_req if member.name == v_name),
            None)
        if value_type is None:
            continue
        _child_schema = child.get_schema(gateway.protocol_version)
        vol_schema = _child_schema.extend(
            {vol.Required(set_req[key].value, msg=msg(key)):
             _child_schema.schema.get(set_req[key].value, val)
             for key, val in schema.get(SCHEMA, {v_name: cv.string}).items()},
            extra=vol.ALLOW_EXTRA)
        try:
            vol_schema(child.values)
        except vol.Invalid as exc:
            level = (logging.WARNING if value_type in child.values
                     else logging.DEBUG)
            _LOGGER.log(
                level,
                "Invalid values: %s: %s platform: node %s child %s: %s",
                child.values, platform, node_id, child.id, exc)
            continue
        dev_id = id(gateway), node_id, child.id, value_type
        validated[platform].append(dev_id)
    return validated
