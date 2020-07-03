"""Support for Proxmox VE."""
from enum import Enum
import logging

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

from .const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PROXMOX_CLIENTS,
)

_LOGGER = logging.getLogger(__name__)


PLATFORMS = ["binary_sensor"]

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

    if DOMAIN not in config:  # setting up with UI
        return True

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


async def async_setup_entry(hass, config_entry) -> bool:
    """Set up ProxmoxVE integration."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    host = config_entry.data[CONF_HOST]

    proxmox_client = ProxmoxClient(
        host,
        config_entry.data[CONF_PORT],
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_REALM],
        config_entry.data[CONF_PASSWORD],
        config_entry.data[CONF_VERIFY_SSL],
    )

    try:
        await hass.async_add_executor_job(proxmox_client.build_client)
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception(exc)
        _LOGGER.error("Could not setup proxmox client, check your config")
        return False

    hass.data[DOMAIN][host] = proxmox_client

    if not proxmox_client:
        _LOGGER.error("Could not setup proxmox client, check your config")
        return False

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


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

    @property
    def host(self):
        """Return host."""
        return self._host

    def build_client(self):
        """Construct the ProxmoxAPI client. Allows inserting the realm within the `user` value."""

        if "@" in self._user:
            user_id = self._user
        else:
            user_id = f"{self._user}@{self._realm}"

        self._proxmox = ProxmoxAPI(
            self._host,
            port=self._port,
            user=user_id,
            password=self._password,
            verify_ssl=self._verify_ssl,
        )

    def get_all_vms(self):
        """Return list of VM in proxmox."""
        vms = []

        for resource in self._proxmox.cluster.resources.get():
            if resource["type"] in ["qemu", "lxc"]:
                vms.append(
                    {
                        "name": resource["name"],
                        "id": resource["id"].split("/")[1],
                        "node": resource["node"],
                        "type": resource["type"],
                    }
                )

        return vms

    def get_nodes(self):
        """Return proxmox nodes list."""
        nodes = []

        for node in self._proxmox.nodes.get():
            nodes.append({"name": node["node"], "status": node["status"]})

        return nodes

    def get_api_client(self):
        """Return the ProxmoxAPI client."""
        return self._proxmox
