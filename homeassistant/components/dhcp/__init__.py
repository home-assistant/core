"""The dhcp integration."""

import fnmatch
import logging
import os
from threading import Event, Thread

from scapy.error import Scapy_Exception
from scapy.layers.dhcp import DHCP
from scapy.layers.l2 import Ether
from scapy.sendrecv import sniff

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.loader import async_get_dhcp

from .const import DOMAIN

FILTER = "udp and (port 67 or 68)"
REQUESTED_ADDR = "requested_addr"
MESSAGE_TYPE = "message-type"
HOSTNAME = "hostname"
MAC_ADDRESS = "macaddress"
IP_ADDRESS = "ip"
DHCP_REQUEST = 3

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the dhcp component."""

    async def _initialize(_):
        dhcp_watcher = DHCPWatcher(hass, await async_get_dhcp(hass))
        dhcp_watcher.start()

        def _stop(*_):
            dhcp_watcher.stop()
            dhcp_watcher.join()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)

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
        self._stop_event = Event()

    def stop(self):
        """Stop the thread."""
        self._stop_event.set()

    def run(self):
        """Start watching for dhcp packets."""
        try:
            sniff(
                filter=FILTER,
                prn=self.handle_dhcp_packet,
                stop_filter=lambda _: self._stop_event.is_set(),
            )
        except (Scapy_Exception, OSError) as ex:
            if os.geteuid() == 0:
                _LOGGER.error("Cannot watch for dhcp packets: %s", ex)
            else:
                _LOGGER.debug(
                    "Cannot watch for dhcp packets without root or CAP_NET_RAW: %s", ex
                )
            return

    def handle_dhcp_packet(self, packet):
        """Process a dhcp packet."""
        if DHCP not in packet:
            return

        options = packet[DHCP].options

        request_type = _decode_dhcp_option(options, MESSAGE_TYPE)
        if request_type != DHCP_REQUEST:
            # DHCP request
            return

        ip_address = _decode_dhcp_option(options, REQUESTED_ADDR)
        hostname = _decode_dhcp_option(options, HOSTNAME)
        mac_address = _format_mac(packet[Ether].src)

        if ip_address is None or hostname is None or mac_address is None:
            return

        data = self._address_data.get(ip_address)

        if data and data[MAC_ADDRESS] == mac_address and data[HOSTNAME] == hostname:
            # If the address data is the same no need
            # to process it
            return

        self._address_data[ip_address] = {MAC_ADDRESS: mac_address, HOSTNAME: hostname}

        self.process_updated_address_data(ip_address, self._address_data[ip_address])

    def process_updated_address_data(self, ip_address, data):
        """Process the address data update."""
        lowercase_hostname = data[HOSTNAME].lower()
        uppercase_mac = data[MAC_ADDRESS].upper()

        _LOGGER.debug(
            "Processing updated address data for %s: mac=%s hostname=%s",
            ip_address,
            uppercase_mac,
            lowercase_hostname,
        )

        for entry in self._integration_matchers:
            if MAC_ADDRESS in entry and not fnmatch.fnmatch(
                uppercase_mac, entry[MAC_ADDRESS]
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
                    data={IP_ADDRESS: ip_address, **data},
                )
            )


def _decode_dhcp_option(dhcp_options, key):
    """Extract and decode data from a packet option."""
    for option in dhcp_options:
        if len(option) < 2 or option[0] != key:
            continue

        value = option[1]
        if value is None or key != HOSTNAME:
            return value

        # hostname is unicode
        try:
            return value.decode()
        except (AttributeError, UnicodeDecodeError):
            return None


def _format_mac(mac_address):
    """Format a mac address for matching."""
    return format_mac(mac_address).replace(":", "")
