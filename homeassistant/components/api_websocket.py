"""Websocket API for Home Assistant."""
import json
import logging

from homeassistant.const import MATCH_ALL
import homeassistant.remote as rem

DEPENDENCIES = 'http',
DOMAIN = 'api_websocket'
WS_EVENT_FORMAT = "event:{}"
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the WebSocket API."""
    hass.wsgi.register_wsgi_app('/api/websocket', websocket_handler(hass))

    return True


def websocket_handler(hass):
    """Return websocket handler."""
    from eventlet import websocket

    connections = set()

    @websocket.WebSocketWSGI
    def handle(wst):
        """Handle websocket connection."""
        _LOGGER.debug('Websocket %s connection opened', id(wst))
        connections.add(wst)
        events = set()

        def event_listener(event):
            """Event listener for wst."""
            if event.event_type not in events:
                return

            msg = WS_EVENT_FORMAT.format(json.dumps(
                event,
                sort_keys=True,
                cls=rem.JSONEncoder
            ))
            _LOGGER.debug('Websocket %s writing event %s', id(wst), msg)
            wst.send(msg)

        try:
            while True:
                msg = wst.wait()
                if msg is None:
                    break

                _LOGGER.debug('Websocket %s received %s', id(wst), msg)

                if msg.startswith('event:subscribe:'):
                    event_type = msg[16:]
                    events.add(event_type)
                    if len(events) == 1:
                        _LOGGER.debug('Websocket %s attaching event listener',
                                      id(wst))
                        hass.bus.listen(MATCH_ALL, event_listener)

        finally:
            _LOGGER.debug('Websocket %s connection closed', id(wst))
            if events:
                _LOGGER.debug('Websocket %s removing event listener', id(wst))
                hass.bus.remove_listener(MATCH_ALL, event_listener)
            connections.remove(wst)

    return handle
