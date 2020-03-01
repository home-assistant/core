"""Support for DD-WRT routers."""
import logging
import re

import aiohttp
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import aiohttp_client, config_validation as cv

_LOGGER = logging.getLogger(__name__)

_DDWRT_DATA_REGEX = re.compile(r"\{(\w+)::([^\}]*)\}")
_MAC_REGEX = re.compile(r"(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})")

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
CONF_WIRELESS_ONLY = "wireless_only"
DEFAULT_WIRELESS_ONLY = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_WIRELESS_ONLY, default=DEFAULT_WIRELESS_ONLY): cv.boolean,
    }
)


async def async_get_scanner(hass, config):
    """Validate the configuration and return a DD-WRT scanner."""
    websession = aiohttp_client.async_get_clientsession(hass)
    try:
        scanner = DdWrtDeviceScanner(config[DOMAIN], websession)
        await scanner.test_connection()
        return scanner
    except ConnectionError:
        return None


class DdWrtDeviceScanner(DeviceScanner):
    """This class queries a wireless router running DD-WRT firmware."""

    def __init__(self, config, websession):
        """Initialize the DD-WRT scanner."""
        self.protocol = "https" if config[CONF_SSL] else "http"
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.wireless_only = config[CONF_WIRELESS_ONLY]
        self.websession = websession
        self.last_results = {}
        self.mac2name = {}

    async def test_connection(self):
        """Test the router is accessible."""
        url = f"{self.protocol}://{self.host}/Status_Wireless.live.asp"
        data = await self.get_ddwrt_data(url)
        if not data:
            raise ConnectionError("Cannot connect to DD-Wrt router")

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._update_info()

        return self.last_results

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        if device not in self.mac2name:
            url = f"{self.protocol}://{self.host}/Status_Lan.live.asp"
            data = await self.get_ddwrt_data(url)

            if not data:
                return None

            dhcp_leases = data.get("dhcp_leases", None)

            if not dhcp_leases:
                return None

            # Remove leading and trailing quotes and spaces
            cleaned_str = dhcp_leases.replace('"', "").replace("'", "").replace(" ", "")
            elements = cleaned_str.split(",")
            num_clients = int(len(elements) / 5)
            self.mac2name = {}
            for idx in range(0, num_clients):
                # The data is a single array
                # every 5 elements represents one host, the MAC
                # is the third element and the name is the first.
                mac_index = (idx * 5) + 2
                if mac_index < len(elements):
                    mac = elements[mac_index]
                    self.mac2name[mac] = elements[idx * 5]

        return self.mac2name.get(device)

    async def _update_info(self):
        """Ensure the information from the DD-WRT router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Checking ARP for %s", self.host)

        endpoint = "Wireless" if self.wireless_only else "Lan"
        url = f"{self.protocol}://{self.host}/Status_{endpoint}.live.asp"
        data = await self.get_ddwrt_data(url)

        if not data:
            _LOGGER.debugt("No ARP data %s", self.host)
            return False

        self.last_results = []

        if self.wireless_only:
            active_clients = data.get("active_wireless", None)
        else:
            active_clients = data.get("arp_table", None)
        if not active_clients:
            return False

        # The DD-WRT UI uses its own data format and then
        # regex's out values so this is done here too
        # Remove leading and trailing single quotes.
        clean_str = active_clients.strip().strip("'")
        elements = clean_str.split("','")

        self.last_results.extend(item for item in elements if _MAC_REGEX.match(item))

        return True

    async def get_ddwrt_data(self, url):
        """Retrieve data from DD-WRT and return parsed result."""
        try:
            response = await self.websession.get(
                url,
                auth=aiohttp.BasicAuth(self.username, self.password),
                verify_ssl=self.verify_ssl,
            )
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.exception("Connection to the router timed out")
            return
        if response.status == 200:
            return _parse_ddwrt_response(await response.text())
        if response.status == 401:
            # Authentication error
            _LOGGER.exception(
                "Failed to authenticate, check your username and password"
            )
            return
        if response.status == 404:
            # Page does not exist
            _LOGGER.exception(
                "DD-WRT status page missing. Is the host a DD-WRT router?"
            )
            return
        _LOGGER.error("Invalid response from DD-WRT: %s", response)


def _parse_ddwrt_response(data_str):
    """Parse the DD-WRT data format."""
    return dict(_DDWRT_DATA_REGEX.findall(data_str))
