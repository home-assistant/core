"""Support for Rflink devices."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import logging

from rflink.protocol import create_rflink_connection
from serial import SerialException
import voluptuous as vol

from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGGING_CHANGED,
)
from homeassistant.core import (
    CoreState,
    Event,
    HassJob,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_DEVICE_REGISTER,
    DATA_ENTITY_GROUP_LOOKUP,
    DATA_ENTITY_LOOKUP,
    EVENT_KEY_COMMAND,
    EVENT_KEY_ID,
    EVENT_KEY_SENSOR,
    SIGNAL_AVAILABILITY,
    SIGNAL_HANDLE_EVENT,
    TMP_ENTITY,
)
from .entity import RflinkCommand
from .utils import identify_event_type

_LOGGER = logging.getLogger(__name__)
LIB_LOGGER = logging.getLogger("rflink")

CONF_IGNORE_DEVICES = "ignore_devices"
CONF_RECONNECT_INTERVAL = "reconnect_interval"
CONF_WAIT_FOR_ACK = "wait_for_ack"
CONF_KEEPALIVE_IDLE = "tcp_keepalive_idle_timer"

DEFAULT_RECONNECT_INTERVAL = 10
DEFAULT_TCP_KEEPALIVE_IDLE_TIMER = 3600
CONNECTION_TIMEOUT = 10

RFLINK_GROUP_COMMANDS = ["allon", "alloff"]

DOMAIN = "rflink"

SERVICE_SEND_COMMAND = "send_command"

SIGNAL_EVENT = "rflink_event"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PORT): vol.Any(cv.port, cv.string),
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_WAIT_FOR_ACK, default=True): cv.boolean,
                vol.Optional(
                    CONF_KEEPALIVE_IDLE, default=DEFAULT_TCP_KEEPALIVE_IDLE_TIMER
                ): int,
                vol.Optional(
                    CONF_RECONNECT_INTERVAL, default=DEFAULT_RECONNECT_INTERVAL
                ): int,
                vol.Optional(CONF_IGNORE_DEVICES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SEND_COMMAND_SCHEMA = vol.Schema(
    {vol.Required(CONF_DEVICE_ID): cv.string, vol.Required(CONF_COMMAND): cv.string}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Rflink component."""
    # Allow entities to register themselves by device_id to be looked up when
    # new rflink events arrive to be handled
    hass.data[DATA_ENTITY_LOOKUP] = {
        EVENT_KEY_COMMAND: defaultdict(list),
        EVENT_KEY_SENSOR: defaultdict(list),
    }
    hass.data[DATA_ENTITY_GROUP_LOOKUP] = {EVENT_KEY_COMMAND: defaultdict(list)}

    # Allow platform to specify function to register new unknown devices
    hass.data[DATA_DEVICE_REGISTER] = {}

    async def async_send_command(call: ServiceCall) -> None:
        """Send Rflink command."""
        _LOGGER.debug("Rflink command for %s", str(call.data))
        if not (
            await RflinkCommand.send_command(
                call.data.get(CONF_DEVICE_ID), call.data.get(CONF_COMMAND)
            )
        ):
            _LOGGER.error("Failed Rflink command for %s", str(call.data))
        else:
            async_dispatcher_send(
                hass,
                SIGNAL_EVENT,
                {
                    EVENT_KEY_ID: call.data.get(CONF_DEVICE_ID),
                    EVENT_KEY_COMMAND: call.data.get(CONF_COMMAND),
                },
            )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, async_send_command, schema=SEND_COMMAND_SCHEMA
    )

    @callback
    def event_callback(event):
        """Handle incoming Rflink events.

        Rflink events arrive as dictionaries of varying content
        depending on their type. Identify the events and distribute
        accordingly.
        """
        event_type = identify_event_type(event)
        _LOGGER.debug("event of type %s: %s", event_type, event)

        # Don't propagate non entity events (eg: version string, ack response)
        if event_type not in hass.data[DATA_ENTITY_LOOKUP]:
            _LOGGER.debug("unhandled event of type: %s", event_type)
            return

        # Lookup entities who registered this device id as device id or alias
        event_id = event.get(EVENT_KEY_ID)

        is_group_event = (
            event_type == EVENT_KEY_COMMAND
            and event[EVENT_KEY_COMMAND] in RFLINK_GROUP_COMMANDS
        )
        if is_group_event:
            entity_ids = hass.data[DATA_ENTITY_GROUP_LOOKUP][event_type].get(
                event_id, []
            )
        else:
            entity_ids = hass.data[DATA_ENTITY_LOOKUP][event_type][event_id]

        _LOGGER.debug("entity_ids: %s", entity_ids)
        if entity_ids:
            # Propagate event to every entity matching the device id
            for entity in entity_ids:
                _LOGGER.debug("passing event to %s", entity)
                async_dispatcher_send(hass, SIGNAL_HANDLE_EVENT.format(entity), event)
        elif not is_group_event:
            # If device is not yet known, register with platform (if loaded)
            if event_type in hass.data[DATA_DEVICE_REGISTER]:
                _LOGGER.debug("device_id not known, adding new device")
                # Add bogus event_id first to avoid race if we get another
                # event before the device is created
                # Any additional events received before the device has been
                # created will thus be ignored.
                hass.data[DATA_ENTITY_LOOKUP][event_type][event_id].append(
                    TMP_ENTITY.format(event_id)
                )
                hass.async_create_task(
                    hass.data[DATA_DEVICE_REGISTER][event_type](event),
                    eager_start=False,
                )
            else:
                _LOGGER.debug("device_id not known and automatic add disabled")

    # When connecting to tcp host instead of serial port (optional)
    host = config[DOMAIN].get(CONF_HOST)
    # TCP port when host configured, otherwise serial port
    port = config[DOMAIN][CONF_PORT]

    keepalive_idle_timer = None
    # TCP KeepAlive only if this is TCP based connection (not serial)
    if host is not None:
        # TCP KEEPALIVE will be enabled if value > 0
        keepalive_idle_timer = config[DOMAIN][CONF_KEEPALIVE_IDLE]
        if keepalive_idle_timer < 0:
            _LOGGER.error(
                (
                    "A bogus TCP Keepalive IDLE timer was provided (%d secs), "
                    "it will be disabled. "
                    "Recommended values: 60-3600 (seconds)"
                ),
                keepalive_idle_timer,
            )
            keepalive_idle_timer = None
        elif keepalive_idle_timer == 0:
            keepalive_idle_timer = None
        elif keepalive_idle_timer <= 30:
            _LOGGER.warning(
                (
                    "A very short TCP Keepalive IDLE timer was provided (%d secs) "
                    "and may produce unexpected disconnections from RFlink device."
                    " Recommended values: 60-3600 (seconds)"
                ),
                keepalive_idle_timer,
            )

    @callback
    def reconnect(_: Exception | None = None) -> None:
        """Schedule reconnect after connection has been unexpectedly lost."""
        # Reset protocol binding before starting reconnect
        RflinkCommand.set_rflink_protocol(None)

        async_dispatcher_send(hass, SIGNAL_AVAILABILITY, False)

        # If HA is not stopping, initiate new connection
        if hass.state is not CoreState.stopping:
            _LOGGER.warning("Disconnected from Rflink, reconnecting")
            hass.async_create_task(connect(), eager_start=False)

    _reconnect_job = HassJob(reconnect, "Rflink reconnect", cancel_on_shutdown=True)

    async def connect():
        """Set up connection and hook it into HA for reconnect/shutdown."""
        _LOGGER.debug("Initiating Rflink connection")

        # Rflink create_rflink_connection decides based on the value of host
        # (string or None) if serial or tcp mode should be used

        # Initiate serial/tcp connection to Rflink gateway
        connection = create_rflink_connection(
            port=port,
            host=host,
            keepalive=keepalive_idle_timer,
            event_callback=event_callback,
            disconnect_callback=reconnect,
            loop=hass.loop,
            ignore=config[DOMAIN][CONF_IGNORE_DEVICES],
        )

        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                transport, protocol = await connection

        except (
            SerialException,
            OSError,
            TimeoutError,
        ):
            reconnect_interval = config[DOMAIN][CONF_RECONNECT_INTERVAL]
            _LOGGER.exception(
                "Error connecting to Rflink, reconnecting in %s", reconnect_interval
            )
            # Connection to Rflink device is lost, make entities unavailable
            async_dispatcher_send(hass, SIGNAL_AVAILABILITY, False)

            async_call_later(hass, reconnect_interval, _reconnect_job)
            return

        # There is a valid connection to a Rflink device now so
        # mark entities as available
        async_dispatcher_send(hass, SIGNAL_AVAILABILITY, True)

        # Bind protocol to command class to allow entities to send commands
        RflinkCommand.set_rflink_protocol(protocol, config[DOMAIN][CONF_WAIT_FOR_ACK])

        # handle shutdown of Rflink asyncio transport
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, lambda x: transport.close()
        )

        _LOGGER.debug("Connected to Rflink")

    hass.async_create_task(connect(), eager_start=False)
    async_dispatcher_connect(hass, SIGNAL_EVENT, event_callback)

    async def handle_logging_changed(_: Event) -> None:
        """Handle logging changed event."""
        if LIB_LOGGER.isEnabledFor(logging.DEBUG):
            await RflinkCommand.send_command("rfdebug", "on")
            _LOGGER.info("RFDEBUG enabled")
        else:
            await RflinkCommand.send_command("rfdebug", "off")
            _LOGGER.info("RFDEBUG disabled")

    # Listen to EVENT_LOGGING_CHANGED to manage the RFDEBUG
    hass.bus.async_listen(EVENT_LOGGING_CHANGED, handle_logging_changed)

    return True
