"""The dhcp integration."""

from abc import abstractmethod
import fnmatch
from ipaddress import ip_address as make_ip_address
import logging
import os
import threading

from scapy.config import conf
from scapy.error import Scapy_Exception
from scapy.layers.dhcp import DHCP
from scapy.layers.l2 import Ether
from scapy.sendrecv import AsyncSniffer

from homeassistant.components.device_tracker.const import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_HOME,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_state_added_domain
from homeassistant.loader import async_get_dhcp
from homeassistant.util.network import is_link_local

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
        address_data = {}
        integration_matchers = await async_get_dhcp(hass)
        watchers = []

        for cls in (DHCPWatcher, DeviceTrackerWatcher):
            watcher = cls(hass, address_data, integration_matchers)
            await watcher.async_start()
            watchers.append(watcher)

        async def _async_stop(*_):
            for watcher in watchers:
                await watcher.async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _initialize)
    return True


class WatcherBase:
    """Base class for dhcp and device tracker watching."""

    def __init__(self, hass, address_data, integration_matchers):
        """Initialize class."""
        super().__init__()

        self.hass = hass
        self._integration_matchers = integration_matchers
        self._address_data = address_data

    def process_client(self, ip_address, hostname, mac_address):
        """Process a client."""
        if is_link_local(make_ip_address(ip_address)):
            # Ignore self assigned addresses
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

            self.create_task(
                self.hass.config_entries.flow.async_init(
                    entry["domain"],
                    context={"source": DOMAIN},
                    data={IP_ADDRESS: ip_address, **data},
                )
            )

    @abstractmethod
    def create_task(self, task):
        """Pass a task to async_add_task based on which context we are in."""


class DeviceTrackerWatcher(WatcherBase):
    """Class to watch dhcp data from routers."""

    def __init__(self, hass, address_data, integration_matchers):
        """Initialize class."""
        super().__init__(hass, address_data, integration_matchers)
        self._unsub = None

    async def async_stop(self):
        """Stop watching for new device trackers."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_start(self):
        """Stop watching for new device trackers."""
        self._unsub = async_track_state_added_domain(
            self.hass, [DEVICE_TRACKER_DOMAIN], self._async_process_device_event
        )
        for state in self.hass.states.async_all(DEVICE_TRACKER_DOMAIN):
            self._async_process_device_state(state)

    @callback
    def _async_process_device_event(self, event: Event):
        """Process a device tracker state change event."""
        self._async_process_device_state(event.data.get("new_state"))

    @callback
    def _async_process_device_state(self, state: State):
        """Process a device tracker state."""
        if state.state != STATE_HOME:
            return

        attributes = state.attributes

        if attributes.get(ATTR_SOURCE_TYPE) != SOURCE_TYPE_ROUTER:
            return

        ip_address = attributes.get(ATTR_IP)
        hostname = attributes.get(ATTR_HOST_NAME)
        mac_address = attributes.get(ATTR_MAC)

        if ip_address is None or hostname is None or mac_address is None:
            return

        self.process_client(ip_address, hostname, _format_mac(mac_address))

    def create_task(self, task):
        """Pass a task to async_create_task since we are in async context."""
        self.hass.async_create_task(task)


class DHCPWatcher(WatcherBase):
    """Class to watch dhcp requests."""

    def __init__(self, hass, address_data, integration_matchers):
        """Initialize class."""
        super().__init__(hass, address_data, integration_matchers)
        self._sniffer = None
        self._started = threading.Event()

    async def async_stop(self):
        """Stop watching for new device trackers."""
        await self.hass.async_add_executor_job(self._stop)

    def _stop(self):
        """Stop the thread."""
        if self._started.is_set():
            self._sniffer.stop()

    async def async_start(self):
        """Start watching for dhcp packets."""
        try:
            _verify_l2socket_creation_permission()
        except (Scapy_Exception, OSError) as ex:
            if os.geteuid() == 0:
                _LOGGER.error("Cannot watch for dhcp packets: %s", ex)
            else:
                _LOGGER.debug(
                    "Cannot watch for dhcp packets without root or CAP_NET_RAW: %s", ex
                )
            return

        self._sniffer = AsyncSniffer(
            filter=FILTER,
            started_callback=self._started.set,
            prn=self.handle_dhcp_packet,
            store=0,
        )
        self._sniffer.start()

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

        self.process_client(ip_address, hostname, mac_address)

    def create_task(self, task):
        """Pass a task to hass.add_job since we are in a thread."""
        self.hass.add_job(task)


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


def _verify_l2socket_creation_permission():
    """Create a socket using the scapy configured l2socket.

    Try to create the socket
    to see if we have permissions
    since AsyncSniffer will do it another
    thread so we will not be able to capture
    any permission or bind errors.
    """
    # disable scapy promiscuous mode as we do not need it
    conf.sniff_promisc = 0
    conf.L2socket()
