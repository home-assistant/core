"""The dhcp integration."""

import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from scapy import DHCP, AsyncSniffer, Ether

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the dhcp component."""

    dhcp_watcher = AsyncSniffer(
        filter="udp and (port 67 or 68)", prn=_handle_dhcp_packet
    )
    dhcp_watcher.start()

    return True


def _extact_option(dhcp_options, key):

    must_decode = ["hostname", "domain", "vendor_class_id"]
    try:
        for i in dhcp_options:
            if i[0] == key:
                # If DHCP Server Returned multiple name servers
                # return all as comma separated string.
                if key == "name_server" and len(i) > 2:
                    return ",".join(i[1:])
                # domain and hostname are binary strings,
                # decode to unicode string before returning
                elif key in must_decode:
                    return i[1].decode()
                else:
                    return i[1]
    except:
        pass


def _handle_dhcp_packet(packet):
    if DHCP not in packet:
        return

    # DHCP request
    if packet[DHCP].options[0][1] == 3:
        requested_addr = _extact_option(packet[DHCP].options, "requested_addr")
        hostname = _extact_option(packet[DHCP].options, "hostname")
        _LOGGER.warning(
            f"Host {hostname} ({packet[Ether].src}) requested {requested_addr}"
        )

    return
