"""Bridge between emulated_roku and Home Assistant."""

import logging

from emulated_roku import EmulatedRokuCommandHandler, EmulatedRokuServer

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, EventOrigin

LOGGER = logging.getLogger(__package__)

EVENT_ROKU_COMMAND = "roku_command"

ATTR_COMMAND_TYPE = "type"
ATTR_SOURCE_NAME = "source_name"
ATTR_KEY = "key"
ATTR_APP_ID = "app_id"

ROKU_COMMAND_KEYDOWN = "keydown"
ROKU_COMMAND_KEYUP = "keyup"
ROKU_COMMAND_KEYPRESS = "keypress"
ROKU_COMMAND_LAUNCH = "launch"


class EmulatedRoku:
    """Manages an emulated_roku server."""

    def __init__(
        self,
        hass,
        name,
        host_ip,
        listen_port,
        advertise_ip,
        advertise_port,
        upnp_bind_multicast,
    ):
        """Initialize the properties."""
        self.hass = hass

        self.roku_usn = name
        self.host_ip = host_ip
        self.listen_port = listen_port

        self.advertise_port = advertise_port
        self.advertise_ip = advertise_ip

        self.bind_multicast = upnp_bind_multicast

        self._api_server = None

        self._unsub_start_listener = None
        self._unsub_stop_listener = None

    async def setup(self):
        """Start the emulated_roku server."""

        class EventCommandHandler(EmulatedRokuCommandHandler):
            """emulated_roku command handler to turn commands into events."""

            def __init__(self, hass):
                self.hass = hass

            def on_keydown(self, roku_usn, key):
                """Handle keydown event."""
                self.hass.bus.async_fire(
                    EVENT_ROKU_COMMAND,
                    {
                        ATTR_SOURCE_NAME: roku_usn,
                        ATTR_COMMAND_TYPE: ROKU_COMMAND_KEYDOWN,
                        ATTR_KEY: key,
                    },
                    EventOrigin.local,
                )

            def on_keyup(self, roku_usn, key):
                """Handle keyup event."""
                self.hass.bus.async_fire(
                    EVENT_ROKU_COMMAND,
                    {
                        ATTR_SOURCE_NAME: roku_usn,
                        ATTR_COMMAND_TYPE: ROKU_COMMAND_KEYUP,
                        ATTR_KEY: key,
                    },
                    EventOrigin.local,
                )

            def on_keypress(self, roku_usn, key):
                """Handle keypress event."""
                self.hass.bus.async_fire(
                    EVENT_ROKU_COMMAND,
                    {
                        ATTR_SOURCE_NAME: roku_usn,
                        ATTR_COMMAND_TYPE: ROKU_COMMAND_KEYPRESS,
                        ATTR_KEY: key,
                    },
                    EventOrigin.local,
                )

            def launch(self, roku_usn, app_id):
                """Handle launch event."""
                self.hass.bus.async_fire(
                    EVENT_ROKU_COMMAND,
                    {
                        ATTR_SOURCE_NAME: roku_usn,
                        ATTR_COMMAND_TYPE: ROKU_COMMAND_LAUNCH,
                        ATTR_APP_ID: app_id,
                    },
                    EventOrigin.local,
                )

        LOGGER.debug(
            "Initializing emulated_roku %s on %s:%s",
            self.roku_usn,
            self.host_ip,
            self.listen_port,
        )

        handler = EventCommandHandler(self.hass)

        self._api_server = EmulatedRokuServer(
            self.hass.loop,
            handler,
            self.roku_usn,
            self.host_ip,
            self.listen_port,
            advertise_ip=self.advertise_ip,
            advertise_port=self.advertise_port,
            bind_multicast=self.bind_multicast,
        )

        async def emulated_roku_stop(event):
            """Wrap the call to emulated_roku.close."""
            LOGGER.debug("Stopping emulated_roku %s", self.roku_usn)
            self._unsub_stop_listener = None
            await self._api_server.close()

        async def emulated_roku_start(event):
            """Wrap the call to emulated_roku.start."""
            try:
                LOGGER.debug("Starting emulated_roku %s", self.roku_usn)
                self._unsub_start_listener = None
                await self._api_server.start()
            except OSError:
                LOGGER.exception(
                    "Failed to start Emulated Roku %s on %s:%s",
                    self.roku_usn,
                    self.host_ip,
                    self.listen_port,
                )
                # clean up inconsistent state on errors
                await emulated_roku_stop(None)
            else:
                self._unsub_stop_listener = self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, emulated_roku_stop
                )

        # start immediately if already running
        if self.hass.state is CoreState.running:
            await emulated_roku_start(None)
        else:
            self._unsub_start_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, emulated_roku_start
            )

        return True

    async def unload(self):
        """Unload the emulated_roku server."""
        LOGGER.debug("Unloading emulated_roku %s", self.roku_usn)

        if self._unsub_start_listener:
            self._unsub_start_listener()
            self._unsub_start_listener = None

        if self._unsub_stop_listener:
            self._unsub_stop_listener()
            self._unsub_stop_listener = None

        await self._api_server.close()

        return True
