"""Component to allow discovering Home Assistant on local network."""
import json
import logging
import select
import socket
import threading
from urllib.parse import urlsplit

from homeassistant.const import (
    __version__, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant import remote

DOMAIN = 'discoverable'
DEPENDENCIES = ['api']

MCAST_IP = "224.0.0.123"
MCAST_PORT = 38123
BIND_IP = "0.0.0.0"

POLL_TIMEOUT = 5

DISCOVER_TIMEOUT = 5
DISCOVERY_QUERY = 'Home Assistants Assemble!'.encode('utf-8')

CONF_EXPOSE_PASSWORD = 'expose_password'
DEFAULT_EXPOSE_PASSWORD = False

_LOGGING = logging.getLogger(__name__)


def setup(hass, config):
    """Set up the server to become discoverable when started."""
    expose_password = config.get(DOMAIN, {}).get(CONF_EXPOSE_PASSWORD,
                                                 DEFAULT_EXPOSE_PASSWORD)
    listener = AssemblyListener(hass, expose_password)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, lambda _: listener.start())

    return True


def get_instance(api_password=None):
    """Discover and instantiate remote HA."""
    info = scan()

    if info is None:
        return None

    parts = urlsplit(info.get('host'))
    api = remote.API(parts.hostname, info.get('api_password', api_password),
                     parts.port, parts.scheme == 'https')
    return remote.HomeAssistant(api)


def scan():
    """Scan the network for Home Assistant instances."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(DISCOVER_TIMEOUT)
    addrs = socket.getaddrinfo(MCAST_IP, MCAST_PORT, socket.AF_INET,
                               socket.SOCK_DGRAM)
    sock.sendto(DISCOVERY_QUERY, addrs[0][4])
    try:
        data = sock.recv(1024)
        return json.loads(data.decode('utf-8'))
    except (socket.timeout, ValueError):
        return None


class AssemblyListener(threading.Thread):
    """Listener for Home Assistant discovery requests."""

    def __init__(self, hass, expose_password):
        """Initialize discovery thread."""
        super().__init__()
        self.hass = hass
        self.expose_password = expose_password
        self.daemon = True

    def run(self):
        """Run discovery thread."""
        should_stop = threading.Event()

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                  lambda _: should_stop.set())

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.getaddrinfo(BIND_IP, MCAST_PORT, socket.AF_INET,
                                  socket.SOCK_DGRAM)[0][4]
        sock.bind(addr)
        sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton(MCAST_IP) + socket.inet_aton(BIND_IP))

        while not should_stop.is_set():
            ready = select.select([sock], [], [], POLL_TIMEOUT)[0]

            if not ready:
                continue

            data, addr = sock.recvfrom(1024)

            if data != DISCOVERY_QUERY:
                _LOGGING.warning('Unexpected data encountered: %s', data)
                continue

            _LOGGING.info('Discovered by %s', addr)
            sock.sendto(json.dumps(self.response()).encode('utf-8'), addr)

    def response(self):
        """Generate discovery response."""
        api = self.hass.config.api
        resp = {
            'content-type': 'home-assistant/server',
            'host': api.base_url,
            'version': __version__,
        }

        if api.api_password is None or self.expose_password:
            resp['api_password'] = api.api_password

        return resp
