"""Support UPNP discovery method that mimics Hue hubs."""
import logging
import select
import socket
import threading

from aiohttp import web

from homeassistant import core
from homeassistant.components.http import HomeAssistantView

from .const import HUE_SERIAL_NUMBER, HUE_UUID

_LOGGER = logging.getLogger(__name__)


class DescriptionXmlView(HomeAssistantView):
    """Handles requests for the description.xml file."""

    url = "/description.xml"
    name = "description:xml"
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request):
        """Handle a GET request."""
        resp_text = f"""<?xml version="1.0" encoding="UTF-8" ?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>http://{self.config.advertise_ip}:{self.config.advertise_port}/</URLBase>
<device>
<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
<friendlyName>Home Assistant Bridge ({self.config.advertise_ip})</friendlyName>
<manufacturer>Royal Philips Electronics</manufacturer>
<manufacturerURL>http://www.philips.com</manufacturerURL>
<modelDescription>Philips hue Personal Wireless Lighting</modelDescription>
<modelName>Philips hue bridge 2015</modelName>
<modelNumber>BSB002</modelNumber>
<modelURL>http://www.meethue.com</modelURL>
<serialNumber>{HUE_SERIAL_NUMBER}</serialNumber>
<UDN>uuid:{HUE_UUID}</UDN>
</device>
</root>
"""

        return web.Response(text=resp_text, content_type="text/xml")


class UPNPResponderThread(threading.Thread):
    """Handle responding to UPNP/SSDP discovery requests."""

    _interrupted = False

    def __init__(
        self,
        host_ip_addr,
        listen_port,
        upnp_bind_multicast,
        advertise_ip,
        advertise_port,
    ):
        """Initialize the class."""
        threading.Thread.__init__(self)

        self.host_ip_addr = host_ip_addr
        self.listen_port = listen_port
        self.upnp_bind_multicast = upnp_bind_multicast
        self.advertise_ip = advertise_ip
        self.advertise_port = advertise_port
        self._ssdp_socket = None

    def run(self):
        """Run the server."""
        # Listen for UDP port 1900 packets sent to SSDP multicast address
        self._ssdp_socket = ssdp_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM
        )
        ssdp_socket.setblocking(False)

        # Required for receiving multicast
        ssdp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        ssdp_socket.setsockopt(
            socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.host_ip_addr)
        )

        ssdp_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton("239.255.255.250") + socket.inet_aton(self.host_ip_addr),
        )

        if self.upnp_bind_multicast:
            ssdp_socket.bind(("", 1900))
        else:
            ssdp_socket.bind((self.host_ip_addr, 1900))

        while True:
            if self._interrupted:
                return

            try:
                read, _, _ = select.select([ssdp_socket], [], [ssdp_socket], 2)

                if ssdp_socket in read:
                    data, addr = ssdp_socket.recvfrom(1024)
                else:
                    # most likely the timeout, so check for interrupt
                    continue
            except OSError as ex:
                if self._interrupted:
                    return

                _LOGGER.error(
                    "UPNP Responder socket exception occurred: %s", ex.__str__
                )
                # without the following continue, a second exception occurs
                # because the data object has not been initialized
                continue

            if "M-SEARCH" in data.decode("utf-8", errors="ignore"):
                _LOGGER.debug("UPNP Responder M-SEARCH method received: %s", data)
                # SSDP M-SEARCH method received, respond to it with our info
                response = self._handle_request(data)

                resp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                resp_socket.sendto(response, addr)
                _LOGGER.debug("UPNP Responder responding with: %s", response)
                resp_socket.close()

    def stop(self):
        """Stop the server."""
        # Request for server
        self._interrupted = True
        if self._ssdp_socket:
            clean_socket_close(self._ssdp_socket)
        self.join()

    def _handle_request(self, data):
        if "upnp:rootdevice" in data.decode("utf-8", errors="ignore"):
            return self._prepare_response(
                "upnp:rootdevice", f"uuid:{HUE_UUID}::upnp:rootdevice"
            )

        return self._prepare_response(
            "urn:schemas-upnp-org:device:basic:1", f"uuid:{HUE_UUID}"
        )

    def _prepare_response(self, search_target, unique_service_name):
        # Note that the double newline at the end of
        # this string is required per the SSDP spec
        response = f"""HTTP/1.1 200 OK
CACHE-CONTROL: max-age=60
EXT:
LOCATION: http://{self.advertise_ip}:{self.advertise_port}/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/1.16.0
hue-bridgeid: {HUE_SERIAL_NUMBER}
ST: {search_target}
USN: {unique_service_name}

"""
        return response.replace("\n", "\r\n").encode("utf-8")


def clean_socket_close(sock):
    """Close a socket connection and logs its closure."""
    _LOGGER.info("UPNP responder shutting down")

    sock.close()
