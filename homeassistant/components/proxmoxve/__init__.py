"""Support for Proxmox VE."""
from enum import Enum
import logging
import time

from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from requests.exceptions import SSLError
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)


DOMAIN = "proxmoxve"
PROXMOX_CLIENTS = "proxmox_clients"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
                        vol.Optional(
                            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                        ): cv.boolean,
                        vol.Required(CONF_NODES): vol.All(
                            cv.ensure_list,
                            [
                                vol.Schema(
                                    {
                                        vol.Required(CONF_NODE): cv.string,
                                        vol.Optional(CONF_VMS, default=[]): [
                                            cv.positive_int
                                        ],
                                        vol.Optional(CONF_CONTAINERS, default=[]): [
                                            cv.positive_int
                                        ],
                                    }
                                )
                            ],
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the component."""

    # Create API Clients for later use
    hass.data[PROXMOX_CLIENTS] = {}
    for entry in config[DOMAIN]:
        host = entry[CONF_HOST]
        port = entry[CONF_PORT]
        user = entry[CONF_USERNAME]
        realm = entry[CONF_REALM]
        password = entry[CONF_PASSWORD]
        verify_ssl = entry[CONF_VERIFY_SSL]

        try:
            # Construct an API client with the given data for the given host
            proxmox_client = ProxmoxClient(
                host, port, user, realm, password, verify_ssl
            )
            proxmox_client.build_client()
        except AuthenticationError:
            _LOGGER.warning(
                "Invalid credentials for proxmox instance %s:%d", host, port
            )
            continue
        except SSLError:
            _LOGGER.error(
                'Unable to verify proxmox server SSL. Try using "verify_ssl: false"'
            )
            continue

        hass.data[PROXMOX_CLIENTS][f"{host}:{port}"] = proxmox_client

    if hass.data[PROXMOX_CLIENTS]:
        hass.helpers.discovery.load_platform(
            "binary_sensor", DOMAIN, {"entries": config[DOMAIN]}, config
        )
        return True

    return False


class ProxmoxItemType(Enum):
    """Represents the different types of machines in Proxmox."""

    qemu = 0
    lxc = 1


class ProxmoxClient:
    """A wrapper for the proxmoxer ProxmoxAPI client."""

    def __init__(self, host, port, user, realm, password, verify_ssl):
        """Initialize the ProxmoxClient."""

        self._host = host
        self._port = port
        self._user = user
        self._realm = realm
        self._password = password
        self._verify_ssl = verify_ssl

        self._proxmox = None
        self._connection_start_time = None

    def build_client(self):
        """Construct the ProxmoxAPI client."""

        self._proxmox = ProxmoxAPI(
            self._host,
            port=self._port,
            user=f"{self._user}@{self._realm}",
            password=self._password,
            verify_ssl=self._verify_ssl,
        )

        self._connection_start_time = time.monotonic()

    def get_api_client(self):
        """Return the ProxmoxAPI client and rebuild it if necessary."""

        connection_age = time.monotonic() - self._connection_start_time

        # Workaround for the Proxmoxer bug where the connection stops working after some time
        if connection_age > 30 * 60:
            self.build_client()

        return self._proxmox
