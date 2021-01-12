"""The dhcp integration."""

import fnmatch
import logging
from threading import Thread

from scapy.all import DHCP, Ether, sniff

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.loader import async_get_dhcp

from .const import DOMAIN

FILTER = "udp and (port 67 or 68)"
REQUESTED_ADDR = "requested_addr"
HOSTNAME = "hostname"
MACADDRESS = "macaddress"
IP = "ip"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the dhcp component."""

    async def _initialize(_):
        dhcp_watcher = DHCPWatcher(hass, await async_get_dhcp(hass))
        dhcp_watcher.start()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, dhcp_watcher.join)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _initialize)
    return True


class DHCPWatcher(Thread):
    """Class to watch dhcp requests."""

    def __init__(self, hass, integration_matchers):
        """Initialize class."""
        super().__init__()

        self.hass = hass
        self.name = "dhcp-discovery"
        self._integration_matchers = integration_matchers
        self._address_data = {}

    def run(self):
        """Start watching for dhcp packets."""
        try:
            sniff(filter=FILTER, prn=self.handle_dhcp_packet)
        except Exception as ex:
            _LOGGER.info("Cannot watch for dhcp packets: %s", ex)
            return

    def handle_dhcp_packet(self, packet):
        """Process a dhcp packet."""
        if DHCP not in packet:
            return

        options = packet[DHCP].options
        if options[0][1] != 3:
            # DHCP request
            return

        try:
            ip = _decode_dhcp_option(options, REQUESTED_ADDR)
            hostname = _decode_dhcp_option(options, HOSTNAME)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug("Error decoding DHCP packet: %s", ex)
            return

        mac = _format_mac(packet[Ether].src)

        if ip is None or hostname is None or mac is None:
            return

        data = self._address_data.get(ip)

        if data and data[MACADDRESS] == mac and data[HOSTNAME] == hostname:
            # If the address data is the same no need
            # to process it
            return

        self._address_data[ip] = {MACADDRESS: mac, HOSTNAME: hostname}

        self.process_updated_address_data(ip, self._address_data[ip])

    def process_updated_address_data(self, ip, data):
        """Process the address data update."""
        lowercase_hostname = data[HOSTNAME].lower()
        uppercase_mac = data[MACADDRESS].upper()

        _LOGGER.debug(
            "Processing updated address data for %s: mac=%s hostname=%s",
            ip,
            uppercase_mac,
            lowercase_hostname,
        )

        for entry in self._integration_matchers:
            if MACADDRESS in entry and not fnmatch.fnmatch(
                uppercase_mac, entry[MACADDRESS]
            ):
                continue

            if HOSTNAME in entry and not fnmatch.fnmatch(
                lowercase_hostname, entry[HOSTNAME]
            ):
                continue

            _LOGGER.debug("Matched %s against %s", data, entry)

            self.hass.add_job(
                self.hass.config_entries.flow.async_init(
                    entry["domain"],
                    context={"source": DOMAIN},
                    data={IP: ip, **data},
                )
            )

        return


def _decode_dhcp_option(dhcp_options, key):
    """Extract and decode data from a packet option."""
    for i in dhcp_options:
        if i[0] != key:
            continue
        # hostname is unicode
        return i[1].decode() if key == HOSTNAME else i[1]


def _format_mac(mac):
    """Format a mac address for matching."""
    return format_mac(mac).replace(":", "")
