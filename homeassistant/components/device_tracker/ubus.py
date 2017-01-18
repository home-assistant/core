"""
Support for OpenWRT (ubus) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ubus/
"""
import json
import logging
from enum import IntEnum

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, DEFAULT_SCAN_INTERVAL, SOURCE_TYPE_ROUTER)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant import util
from homeassistant.helpers.event import track_point_in_utc_time

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})


# From http://lxr.mein.io/source/ubus/ubusmsg.h#L99
class UbusStatus(IntEnum):
    """Ubus status codes."""
    UBUS_STATUS_OK = 0
    UBUS_STATUS_INVALID_COMMAND = 1
    UBUS_STATUS_INVALID_ARGUMENT = 2
    UBUS_STATUS_METHOD_NOT_FOUND = 3
    UBUS_STATUS_NOT_FOUND = 4
    UBUS_STATUS_NO_DATA = 5
    UBUS_STATUS_PERMISSION_DENIED = 6
    UBUS_STATUS_TIMEOUT = 7
    UBUS_STATUS_NOT_SUPPORTED = 8
    UBUS_STATUS_UNKNOWN_ERROR = 9
    UBUS_STATUS_CONNECTION_FAILED = 10


class UbusException(Exception):
    """UbusException gets raised when receiving errors from ubus."""
    pass


class UbusDeviceScanner:
    """
    This class queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.url = 'http://{}/ubus'.format(host)
        self.session_id = _get_session_id(self.url, username, password)

    def update(self, see):
        """Fetch clients and leases from the router."""
        clients = self._get_devices()
        leases = self._get_leases()

        for client in clients:
            mac = client["mac"].replace(":", "").lower()
            for lease in leases:
                if lease["mac"] == mac:
                    lease.update(client)
                    # example lease
                    # {'ip': '192.168.250.186', 'inactive': 3530,
                    # 'hostname': 'XXXX', 'valid': -23916,
                    # 'mac': '50:C7:BF:XX:XX:XX', 'noise': -95, 'signal': -48}
                    extra_attrs = {
                        "ip": lease["ip"],
                        "signal": lease["signal"],
                        "noise": lease["noise"]
                    }
                    # _LOGGER.info("Seen: %s", lease)
                    see(mac=lease["mac"], host_name=lease["hostname"],
                        source_type=SOURCE_TYPE_ROUTER,
                        attributes=extra_attrs)

    def _get_devices(self):
        """Request all connected devices."""
        clients = []

        try:
            ifaces = _req_json_rpc(self.url, self.session_id,
                                   "call", "iwinfo", "devices")
        except UbusException as ex:
            _LOGGER.error("Unable to fetch interfaces: %s", ex)
            return

        # _LOGGER.debug("Found %s ifaces: %s", len(ifaces), ifaces)
        for iface in ifaces["devices"]:
            devices = _req_json_rpc(self.url, self.session_id,
                                    "call", "iwinfo", "assoclist",
                                    device=iface)
            if "results" in devices:
                for dev in devices["results"]:
                    # _LOGGER.debug("device: %s", dev)
                    clients.append(dev)

        # example client
        # [{'signal': -47, 'inactive': 310,
        # 'tx': {'mcs': 7, '40mhz': False, 'rate': 65000, 'short_gi': False},
        # 'mac': 'F0:B4:29:XX:XX:XX',
        # 'rx': {'mcs': 7, '40mhz': False, 'rate': 72200, 'short_gi': True},
        # 'noise': -95}]
        # _LOGGER.info("Found %s clients: %s", len(clients),
        #             [client["mac"] for client in clients])

        return clients

    def _get_leases(self):
        """Get all DHCP leases to obtain hostnames."""
        leases = []
        for ip_version in ["ipv4leases", "ipv6leases"]:
            lease_res = _req_json_rpc(self.url, self.session_id,
                                      "call", "dhcp", ip_version)
            for network in lease_res["device"]:
                # _LOGGER.debug("Checking network %s" % network)
                for lease in lease_res["device"][network]["leases"]:
                    # _LOGGER.debug("[%s] client: %s", network, lease)
                    leases.append(lease)

        # example lease
        # {'mac': '286c07xxxxxx', 'valid': -7471,
        # 'hostname': 'XXXXX','ip': '192.168.250.132'}

        return leases


def _req_json_rpc(url, session_id, rpcmethod, subsystem, method, **params):
    """Perform one JSON RPC operation."""

    data = {"jsonrpc": "2.0",
            "id": 1,
            "method": rpcmethod,
            "params": [session_id,
                       subsystem,
                       method,
                       params]}
    data_json = json.dumps(data)
    _LOGGER.debug("> %s (%s)", data["method"], data["params"])

    try:
        res = requests.post(url, data=data_json, timeout=5)

    except requests.exceptions.Timeout:
        _LOGGER.error("Got got timeout when doing a request on %s", url)
        return

    _LOGGER.debug("< %s", res.text)

    if res.status_code != 200:
        _LOGGER.error("Got invalid status for the call: %s", res.raw)
        return

    response = res.json()

    if rpcmethod == "call":
        if "error" in response:
            _LOGGER.error("Got error from ubus for call %s(%s): %s",
                          data["method"], data["params"], response["error"])
            raise UbusException(response["error"])

        if "result" not in response:
            _LOGGER.error("Ubus reply has no result dict: %s", response)
            raise UbusException("Got no result: %s" % response)

        retcode = response["result"][0]
        if retcode != UbusStatus.UBUS_STATUS_OK:
            _LOGGER.error("Got error from ubus: %s", UbusStatus(retcode))
            raise UbusException("Got ubus error: %s" % UbusStatus(retcode))

        res = response["result"][1]
        return res
    else:
        return response["result"]


def _get_session_id(url, username, password):
    """Get the authentication token for the given host+username+password."""
    res = _req_json_rpc(url, "00000000000000000000000000000000", 'call',
                        'session', 'login', username=username,
                        password=password)

    # example session
    # note, sessions do not seem to expire..
    # {'ubus_rpc_session': '95533928ec0bde5603c408c0eaa314d3',
    # 'acls': {'uci': {'dhcp': ['read']},
    #          'ubus': {'iwinfo': ['devices', 'assoclist'],
    #          'session': ['access', 'login'],
    #          'dhcp': ['ipv4leases', 'ipv6leases']},
    # 'access-group': {'hass': ['read'], 'unauthenticated': ['read']}},
    # 'expires': 300, 'timeout': 300, 'data': {'username': 'hass'}}

    _LOGGER.debug("Got session, verifying required permissions: %s", res)
    if "acls" not in res:
        raise UbusException("Session does not have acls: %s" % res)

    if not res["acls"]["ubus"]:
        raise UbusException("Session does not have ubus acl: %s" % res)

    ubus_acls = res["acls"]["ubus"]
    if not ubus_acls.keys() & {'dhcp', 'iwinfo'}:
        raise UbusException("ACL 'dhcp' or 'iwinfo' missing: %s" % res)

    _LOGGER.debug("Got necessary permissions, we're good to go!")

    return res["ubus_rpc_session"]


def setup_scanner(hass, config, see):
    """Setup an endpoint for the ubus logger."""
    try:
        _LOGGER.info("Trying to start the scanner..")
        scanner = UbusDeviceScanner(config)
        interval = DEFAULT_SCAN_INTERVAL
        _LOGGER.info("Started ubustracker with interval=%s", interval)

        def update(now):
            """Update all the hosts on every interval time."""
            _LOGGER.info("Update called..")
            scanner.update(see)
            track_point_in_utc_time(hass, update, now + interval)
            return True

        return update(util.dt.utcnow())
    except UbusException as ex:
        _LOGGER.error("Got exception: %s", ex)
        return False

    return True
