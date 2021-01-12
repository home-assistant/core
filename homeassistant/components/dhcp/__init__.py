"""The dhcp integration."""

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from scapy.all import DHCP, AsyncSniffer, Ether

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.device_registry import format_mac

FILTER = "udp and (port 67 or 68)"
REQUESTED_ADDR = "requested_addr"
HOSTNAME = "hostname"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the dhcp component."""

    async def _initialize(_):
        try:
            dhcp_watcher = AsyncSniffer(filter=FILTER, prn=_handle_dhcp_packet)
            dhcp_watcher.start()
        except Exception as ex:
            _LOGGER.info("Cannot watch for dhcp packets: %s", ex)
            return

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, dhcp_watcher.stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _initialize)
    return True


def _decode_option(dhcp_options, key):
    """Extract and decode data from a packet option."""
    for i in dhcp_options:
        if i[0] != key:
            continue
        # hostname is unicode
        return i[1].decode() if key == HOSTNAME else i[i]


def _handle_dhcp_packet(packet):
    """Process a dhcp packet."""
    if DHCP not in packet:
        return

    # DHCP request
    try:
        if packet[DHCP].options[0][1] == 3:
            options = packet[DHCP].options
            ip_address = _decode_option(options, REQUESTED_ADDR)
            hostname = _decode_option(options, HOSTNAME)
            mac = format_mac(packet[Ether].src)

            _LOGGER.warning(f"Host {hostname} ({mac}) requested {ip_address}")
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug("Error decoding DHCP packet: %s", ex)
        pass

    return
