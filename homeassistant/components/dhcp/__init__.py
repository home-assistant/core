"""The dhcp integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable, Iterable
import contextlib
from dataclasses import dataclass
from datetime import timedelta
from fnmatch import translate
from functools import lru_cache
from ipaddress import ip_address as make_ip_address
import logging
import os
import re
import threading
from typing import TYPE_CHECKING, Any, Final, cast

from aiodiscover import DiscoverHosts
from aiodiscover.discovery import (
    HOSTNAME as DISCOVERY_HOSTNAME,
    IP_ADDRESS as DISCOVERY_IP_ADDRESS,
    MAC_ADDRESS as DISCOVERY_MAC_ADDRESS,
)
from scapy.config import conf
from scapy.error import Scapy_Exception

from homeassistant import config_entries
from homeassistant.components.device_tracker import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    CONNECTED_DEVICE_REGISTERED,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SourceType,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_HOME,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceRegistry,
    async_get,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_added_domain,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType, EventType
from homeassistant.loader import DHCPMatcher, async_get_dhcp
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.network import is_invalid, is_link_local, is_loopback

from .const import DOMAIN

if TYPE_CHECKING:
    from scapy.packet import Packet
    from scapy.sendrecv import AsyncSniffer

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

FILTER = "udp and (port 67 or 68)"
REQUESTED_ADDR = "requested_addr"
MESSAGE_TYPE = "message-type"
HOSTNAME: Final = "hostname"
MAC_ADDRESS: Final = "macaddress"
IP_ADDRESS: Final = "ip"
REGISTERED_DEVICES: Final = "registered_devices"
DHCP_REQUEST = 3
SCAN_INTERVAL = timedelta(minutes=60)


_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DhcpServiceInfo(BaseServiceInfo):
    """Prepared info from dhcp entries."""

    ip: str
    hostname: str
    macaddress: str


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the dhcp component."""
    watchers: list[WatcherBase] = []
    address_data: dict[str, dict[str, str]] = {}
    integration_matchers = await async_get_dhcp(hass)
    # For the passive classes we need to start listening
    # for state changes and connect the dispatchers before
    # everything else starts up or we will miss events
    for passive_cls in (DeviceTrackerRegisteredWatcher, DeviceTrackerWatcher):
        passive_watcher = passive_cls(hass, address_data, integration_matchers)
        await passive_watcher.async_start()
        watchers.append(passive_watcher)

    async def _initialize(event: Event) -> None:
        for active_cls in (DHCPWatcher, NetworkWatcher):
            active_watcher = active_cls(hass, address_data, integration_matchers)
            await active_watcher.async_start()
            watchers.append(active_watcher)

        async def _async_stop(event: Event) -> None:
            for watcher in watchers:
                await watcher.async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _initialize)
    return True


class WatcherBase(ABC):
    """Base class for dhcp and device tracker watching."""

    def __init__(
        self,
        hass: HomeAssistant,
        address_data: dict[str, dict[str, str]],
        integration_matchers: list[DHCPMatcher],
    ) -> None:
        """Initialize class."""
        super().__init__()

        self.hass = hass
        self._integration_matchers = integration_matchers
        self._address_data = address_data

    @abstractmethod
    async def async_stop(self) -> None:
        """Stop the watcher."""

    @abstractmethod
    async def async_start(self) -> None:
        """Start the watcher."""

    def process_client(self, ip_address: str, hostname: str, mac_address: str) -> None:
        """Process a client."""
        return run_callback_threadsafe(
            self.hass.loop,
            self.async_process_client,
            ip_address,
            hostname,
            mac_address,
        ).result()

    @callback
    def async_process_client(
        self, ip_address: str, hostname: str, mac_address: str
    ) -> None:
        """Process a client."""
        made_ip_address = make_ip_address(ip_address)

        if (
            is_link_local(made_ip_address)
            or is_loopback(made_ip_address)
            or is_invalid(made_ip_address)
        ):
            # Ignore self assigned addresses, loopback, invalid
            return

        data = self._address_data.get(ip_address)
        if (
            data
            and data[MAC_ADDRESS] == mac_address
            and data[HOSTNAME].startswith(hostname)
        ):
            # If the address data is the same no need
            # to process it
            return

        data = {MAC_ADDRESS: mac_address, HOSTNAME: hostname}
        self._address_data[ip_address] = data

        lowercase_hostname = hostname.lower()
        uppercase_mac = mac_address.upper()

        _LOGGER.debug(
            "Processing updated address data for %s: mac=%s hostname=%s",
            ip_address,
            uppercase_mac,
            lowercase_hostname,
        )

        matched_domains = set()
        device_domains = set()

        dev_reg: DeviceRegistry = async_get(self.hass)
        if device := dev_reg.async_get_device(
            connections={(CONNECTION_NETWORK_MAC, uppercase_mac)}
        ):
            for entry_id in device.config_entries:
                if entry := self.hass.config_entries.async_get_entry(entry_id):
                    device_domains.add(entry.domain)

        for matcher in self._integration_matchers:
            domain = matcher["domain"]

            if matcher.get(REGISTERED_DEVICES) and domain not in device_domains:
                continue

            if (
                matcher_mac := matcher.get(MAC_ADDRESS)
            ) is not None and not _memorized_fnmatch(uppercase_mac, matcher_mac):
                continue

            if (
                matcher_hostname := matcher.get(HOSTNAME)
            ) is not None and not _memorized_fnmatch(
                lowercase_hostname, matcher_hostname
            ):
                continue

            _LOGGER.debug("Matched %s against %s", data, matcher)
            matched_domains.add(domain)

        for domain in matched_domains:
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_DHCP},
                DhcpServiceInfo(
                    ip=ip_address,
                    hostname=lowercase_hostname,
                    macaddress=mac_address,
                ),
            )


class NetworkWatcher(WatcherBase):
    """Class to query ptr records routers."""

    def __init__(
        self,
        hass: HomeAssistant,
        address_data: dict[str, dict[str, str]],
        integration_matchers: list[DHCPMatcher],
    ) -> None:
        """Initialize class."""
        super().__init__(hass, address_data, integration_matchers)
        self._unsub: Callable[[], None] | None = None
        self._discover_hosts: DiscoverHosts | None = None
        self._discover_task: asyncio.Task | None = None

    async def async_stop(self) -> None:
        """Stop scanning for new devices on the network."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._discover_task:
            self._discover_task.cancel()
            self._discover_task = None

    async def async_start(self) -> None:
        """Start scanning for new devices on the network."""
        self._discover_hosts = DiscoverHosts()
        self._unsub = async_track_time_interval(
            self.hass,
            self.async_start_discover,
            SCAN_INTERVAL,
            name="DHCP network watcher",
        )
        self.async_start_discover()

    @callback
    def async_start_discover(self, *_: Any) -> None:
        """Start a new discovery task if one is not running."""
        if self._discover_task and not self._discover_task.done():
            return
        self._discover_task = self.hass.async_create_task(self.async_discover())

    async def async_discover(self) -> None:
        """Process discovery."""
        assert self._discover_hosts is not None
        for host in await self._discover_hosts.async_discover():
            self.async_process_client(
                host[DISCOVERY_IP_ADDRESS],
                host[DISCOVERY_HOSTNAME],
                _format_mac(host[DISCOVERY_MAC_ADDRESS]),
            )


class DeviceTrackerWatcher(WatcherBase):
    """Class to watch dhcp data from routers."""

    def __init__(
        self,
        hass: HomeAssistant,
        address_data: dict[str, dict[str, str]],
        integration_matchers: list[DHCPMatcher],
    ) -> None:
        """Initialize class."""
        super().__init__(hass, address_data, integration_matchers)
        self._unsub: Callable[[], None] | None = None

    async def async_stop(self) -> None:
        """Stop watching for new device trackers."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_start(self) -> None:
        """Stop watching for new device trackers."""
        self._unsub = async_track_state_added_domain(
            self.hass, [DEVICE_TRACKER_DOMAIN], self._async_process_device_event
        )
        for state in self.hass.states.async_all(DEVICE_TRACKER_DOMAIN):
            self._async_process_device_state(state)

    @callback
    def _async_process_device_event(
        self, event: EventType[EventStateChangedData]
    ) -> None:
        """Process a device tracker state change event."""
        self._async_process_device_state(event.data["new_state"])

    @callback
    def _async_process_device_state(self, state: State | None) -> None:
        """Process a device tracker state."""
        if state is None or state.state != STATE_HOME:
            return

        attributes = state.attributes

        if attributes.get(ATTR_SOURCE_TYPE) != SourceType.ROUTER:
            return

        ip_address = attributes.get(ATTR_IP)
        hostname = attributes.get(ATTR_HOST_NAME, "")
        mac_address = attributes.get(ATTR_MAC)

        if ip_address is None or mac_address is None:
            return

        self.async_process_client(ip_address, hostname, _format_mac(mac_address))


class DeviceTrackerRegisteredWatcher(WatcherBase):
    """Class to watch data from device tracker registrations."""

    def __init__(
        self,
        hass: HomeAssistant,
        address_data: dict[str, dict[str, str]],
        integration_matchers: list[DHCPMatcher],
    ) -> None:
        """Initialize class."""
        super().__init__(hass, address_data, integration_matchers)
        self._unsub: Callable[[], None] | None = None

    async def async_stop(self) -> None:
        """Stop watching for device tracker registrations."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_start(self) -> None:
        """Stop watching for device tracker registrations."""
        self._unsub = async_dispatcher_connect(
            self.hass, CONNECTED_DEVICE_REGISTERED, self._async_process_device_data
        )

    @callback
    def _async_process_device_data(self, data: dict[str, str | None]) -> None:
        """Process a device tracker state."""
        ip_address = data[ATTR_IP]
        hostname = data[ATTR_HOST_NAME] or ""
        mac_address = data[ATTR_MAC]

        if ip_address is None or mac_address is None:
            return

        self.async_process_client(ip_address, hostname, _format_mac(mac_address))


class DHCPWatcher(WatcherBase):
    """Class to watch dhcp requests."""

    def __init__(
        self,
        hass: HomeAssistant,
        address_data: dict[str, dict[str, str]],
        integration_matchers: list[DHCPMatcher],
    ) -> None:
        """Initialize class."""
        super().__init__(hass, address_data, integration_matchers)
        self._sniffer: AsyncSniffer | None = None
        self._started = threading.Event()

    async def async_stop(self) -> None:
        """Stop watching for new device trackers."""
        await self.hass.async_add_executor_job(self._stop)

    def _stop(self) -> None:
        """Stop the thread."""
        if self._started.is_set():
            assert self._sniffer is not None
            self._sniffer.stop()

    async def async_start(self) -> None:
        """Start watching for dhcp packets."""
        await self.hass.async_add_executor_job(self._start)

    def _start(self) -> None:
        """Start watching for dhcp packets."""
        # Local import because importing from scapy has side effects such as opening
        # sockets
        from scapy import arch  # pylint: disable=import-outside-toplevel # noqa: F401
        from scapy.layers.dhcp import DHCP  # pylint: disable=import-outside-toplevel
        from scapy.layers.inet import IP  # pylint: disable=import-outside-toplevel
        from scapy.layers.l2 import Ether  # pylint: disable=import-outside-toplevel

        #
        # Importing scapy.sendrecv will cause a scapy resync which will
        # import scapy.arch.read_routes which will import scapy.sendrecv
        #
        # We avoid this circular import by importing arch above to ensure
        # the module is loaded and avoid the problem
        #
        from scapy.sendrecv import (  # pylint: disable=import-outside-toplevel
            AsyncSniffer,
        )

        def _handle_dhcp_packet(packet: Packet) -> None:
            """Process a dhcp packet."""
            if DHCP not in packet:
                return

            options_dict = _dhcp_options_as_dict(packet[DHCP].options)
            if options_dict.get(MESSAGE_TYPE) != DHCP_REQUEST:
                # Not a DHCP request
                return

            ip_address = options_dict.get(REQUESTED_ADDR) or cast(str, packet[IP].src)
            assert isinstance(ip_address, str)
            hostname = ""
            if (hostname_bytes := options_dict.get(HOSTNAME)) and isinstance(
                hostname_bytes, bytes
            ):
                with contextlib.suppress(AttributeError, UnicodeDecodeError):
                    hostname = hostname_bytes.decode()
            mac_address = _format_mac(cast(str, packet[Ether].src))

            if ip_address is not None and mac_address is not None:
                self.process_client(ip_address, hostname, mac_address)

        # disable scapy promiscuous mode as we do not need it
        conf.sniff_promisc = 0

        try:
            _verify_l2socket_setup(FILTER)
        except (Scapy_Exception, OSError) as ex:
            if os.geteuid() == 0:
                _LOGGER.error("Cannot watch for dhcp packets: %s", ex)
            else:
                _LOGGER.debug(
                    "Cannot watch for dhcp packets without root or CAP_NET_RAW: %s", ex
                )
            return

        try:
            _verify_working_pcap(FILTER)
        except (Scapy_Exception, ImportError) as ex:
            _LOGGER.error(
                "Cannot watch for dhcp packets without a functional packet filter: %s",
                ex,
            )
            return

        self._sniffer = AsyncSniffer(
            filter=FILTER,
            started_callback=self._started.set,
            prn=_handle_dhcp_packet,
            store=0,
        )

        self._sniffer.start()
        if self._sniffer.thread:
            self._sniffer.thread.name = self.__class__.__name__


def _dhcp_options_as_dict(
    dhcp_options: Iterable[tuple[str, int | bytes | None]]
) -> dict[str, str | int | bytes | None]:
    """Extract data from packet options as a dict."""
    return {option[0]: option[1] for option in dhcp_options if len(option) >= 2}


def _format_mac(mac_address: str) -> str:
    """Format a mac address for matching."""
    return format_mac(mac_address).replace(":", "")


def _verify_l2socket_setup(cap_filter: str) -> None:
    """Create a socket using the scapy configured l2socket.

    Try to create the socket
    to see if we have permissions
    since AsyncSniffer will do it another
    thread so we will not be able to capture
    any permission or bind errors.
    """
    conf.L2socket(filter=cap_filter)


def _verify_working_pcap(cap_filter: str) -> None:
    """Verify we can create a packet filter.

    If we cannot create a filter we will be listening for
    all traffic which is too intensive.
    """
    # Local import because importing from scapy has side effects such as opening
    # sockets
    from scapy.arch.common import (  # pylint: disable=import-outside-toplevel
        compile_filter,
    )

    compile_filter(cap_filter)


@lru_cache(maxsize=4096, typed=True)
def _compile_fnmatch(pattern: str) -> re.Pattern:
    """Compile a fnmatch pattern."""
    return re.compile(translate(pattern))


@lru_cache(maxsize=1024, typed=True)
def _memorized_fnmatch(name: str, pattern: str) -> bool:
    """Memorized version of fnmatch that has a larger lru_cache.

    The default version of fnmatch only has a lru_cache of 256 entries.
    With many devices we quickly reach that limit and end up compiling
    the same pattern over and over again.

    DHCP has its own memorized fnmatch with its own lru_cache
    since the data is going to be relatively the same
    since the devices will not change frequently
    """
    return bool(_compile_fnmatch(pattern).match(name))
