"""Bridge between emulated_roku and Home Assistant."""
import logging

from homeassistant.core import EventOrigin

LOGGER = logging.getLogger('homeassistant.components.emulated_roku')

EVENT_ROKU_COMMAND = 'roku_command'

ATTR_COMMAND_TYPE = 'type'
ATTR_SOURCE_NAME = 'source_name'
ATTR_KEY = 'key'
ATTR_APP_ID = 'app_id'

ROKU_COMMAND_KEYDOWN = 'keydown'
ROKU_COMMAND_KEYUP = 'keyup'
ROKU_COMMAND_KEYPRESS = 'keypress'
ROKU_COMMAND_LAUNCH = 'launch'


class EmulatedRoku:
    """Manages an emulated_roku server."""

    def __init__(self, hass, name, host_ip, listen_port,
                 advertise_ip, advertise_port, upnp_bind_multicast):
        """Initialize the properties."""
        self.hass = hass

        self.roku_usn = name
        self.host_ip = host_ip
        self.listen_port = listen_port

        self.advertise_port = advertise_port
        self.advertise_ip = advertise_ip

        self.bind_multicast = upnp_bind_multicast

        self.api_server = None
        self.ssdp_server = None

    async def async_setup(self):
        """Start the emulated_roku server."""
        from emulated_roku import RokuCommandHandler, make_roku_api

        class EventCommandHandler(RokuCommandHandler):
            """emulated_roku command handler to turn commands into events."""

            def __init__(self, hass):
                self.hass = hass

            def on_keydown(self, roku_usn, key):
                """Handle keydown event."""
                self.hass.bus.async_fire(EVENT_ROKU_COMMAND, {
                    ATTR_SOURCE_NAME: roku_usn,
                    ATTR_COMMAND_TYPE: ROKU_COMMAND_KEYDOWN,
                    ATTR_KEY: key
                }, EventOrigin.local)

            def on_keyup(self, roku_usn, key):
                """Handle keyup event."""
                self.hass.bus.async_fire(EVENT_ROKU_COMMAND, {
                    ATTR_SOURCE_NAME: roku_usn,
                    ATTR_COMMAND_TYPE: ROKU_COMMAND_KEYUP,
                    ATTR_KEY: key
                }, EventOrigin.local)

            def on_keypress(self, roku_usn, key):
                """Handle keypress event."""
                self.hass.bus.async_fire(EVENT_ROKU_COMMAND, {
                    ATTR_SOURCE_NAME: roku_usn,
                    ATTR_COMMAND_TYPE: ROKU_COMMAND_KEYPRESS,
                    ATTR_KEY: key
                }, EventOrigin.local)

            def launch(self, roku_usn, app_id):
                """Handle launch event."""
                self.hass.bus.async_fire(EVENT_ROKU_COMMAND, {
                    ATTR_SOURCE_NAME: roku_usn,
                    ATTR_COMMAND_TYPE: ROKU_COMMAND_LAUNCH,
                    ATTR_APP_ID: app_id
                }, EventOrigin.local)

        handler = EventCommandHandler(self.hass)

        LOGGER.debug("Intializing emulated_roku %s on %s:%s",
                     self.roku_usn, self.host_ip, self.listen_port)

        (self.ssdp_server, _), self.api_server = await make_roku_api(
            self.hass.loop, handler,
            self.roku_usn, self.host_ip, self.listen_port,
            advertise_ip=self.advertise_ip,
            advertise_port=self.advertise_port,
            bind_multicast=self.bind_multicast
        )

        return True

    def stop(self):
        """Stop the emulated_roku server."""
        LOGGER.debug("Stopping emulated_roku %s", self.roku_usn)
        if self.ssdp_server:
            self.ssdp_server.close()
        if self.api_server:
            self.api_server.close()
        return True
