"""
Support for OpenWRT (luci) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.openwrt/
"""
import logging
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_SSL, CONF_VERIFY_SSL)
from homeassistant.exceptions import HomeAssistantError


_LOGGER = logging.getLogger(__name__)

CONF_RADIO = 'radio'
CONF_API = 'api'
CONF_DNSLOOKUP = 'dnslookup'
DEFAULT_VERIFY_SSL = True
CONF_DHCP_SOFTWARE = 'dhcp_software'
DEFAULT_DHCP_SOFTWARE = 'dnsmasq'
DHCP_SOFTWARES = [
    'dnsmasq',
    'odhcpd'
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_API, default='wireless'): cv.string,
    vol.Optional(
        CONF_RADIO, default='autodetect'): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): vol.Any(
        cv.boolean, cv.isfile),
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_DNSLOOKUP, default=True): cv.boolean,
    vol.Optional(CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE):
        vol.In(DHCP_SOFTWARES)
})


def get_scanner(hass, config):
    """Validate the configuration and return a Luci scanner."""
    if config[DOMAIN][CONF_API] in ['jsonrpc', 'luci']:
        scanner = LuciDeviceScanner(config[DOMAIN])
    elif config[DOMAIN][CONF_API] == 'ubus':
        dhcp_sw = config[DOMAIN][CONF_DHCP_SOFTWARE]
        if dhcp_sw == 'dnsmasq':
            scanner = DnsmasqUbusDeviceScanner(config[DOMAIN])
        else:
            scanner = OdhcpdUbusDeviceScanner(config[DOMAIN])
    elif config[DOMAIN][CONF_API] == 'wireless':
        scanner = LuciWirelessDeviceScanner(config[DOMAIN])
    else:
        _LOGGER.error("Unknown api %s using api: wireless",
                      config[CONF_API])
        scanner = LuciWirelessDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class LuciWirelessDeviceScanner(DeviceScanner):
    """This class queries a wireless router running OpenWrt firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.radio = config[CONF_RADIO]
        self.verify = config[CONF_VERIFY_SSL]
        if config[CONF_SSL]:
            self.proto = 'https'
            if not self.verify and config[CONF_SSL]:
                import urllib3
                urllib3.disable_warnings(
                    urllib3.exceptions.InsecureRequestWarning)
        else:
            self.proto = 'http'
        self.last_results = []
        self.dns_lookup = config[CONF_DNSLOOKUP]
        self.missed_host = False
        self.success_init = self.login()
        text = self.get_wireless_info()
        if self.radio == 'autodetect':
            self.detectradio(text)
        self.parse_hosts(text)
        _LOGGER.info("Starting openwrt wireless scanner %s://%s radio:%s",
                     self.proto, self.host, config[CONF_RADIO])

    def login(self):
        """Try to login to luci."""
        self.session = requests.Session()
        url = '{}://{}/cgi-bin/luci/'.format(self.proto, self.host)
        data = {'luci_username': self.username, 'luci_password': self.password}
        try:
            res = self.session.post(url, data=data,
                                    verify=self.verify, timeout=5)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot login %s://%s : %s",
                          self.proto, self.host, exception.__class__.__name__)
            return False
        if res.status_code == 302 or res.status_code == 200:
            _LOGGER.debug("login %s://%s status_code: %s succeeded",
                          self.proto, self.host, res.status_code)
            return True
        else:
            _LOGGER.error("Cannot login to %s://%s status_code: %d",
                          self.proto, self.host, res.status_code)
        return False

    def get_wireless_info(self):
        """Get the wireless html page."""
        url = '{}://{}/cgi-bin/luci/admin/network/wireless'.format(
            self.proto, self.host)
        try:
            res = self.session.post(url, verify=self.verify, timeout=5)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot get wireless info %s://%s : %s",
                          self.proto, self.host, exception.__class__.__name__)
            return None
        if res.status_code == 200:
            _LOGGER.info("Retrieved wireless info from %s://%s",
                         self.proto, self.host)
            return res.text
        return None

    def detectradio(self, text):
        """Try to find radios/networks."""
        import json
        startstring = 'var wifidevs = '
        start = text.find(startstring)
        if start > 0:
            start += len(startstring)
            endstring = ";\n"
            end = text.find(endstring, start)
            if end > 0:
                radio = json.loads(text[start:end])
                self.radio = ','.join(radio.keys())
                _LOGGER.info("Found radio: %s on %s://%s",
                             self.radio, self.proto, self.host)
                return True
        _LOGGER.error("Cannot autodetect radio from %s://%s",
                      self.proto, self.host)
        return False

    def parse_hosts(self, text):
        """Try to find hosts in luci."""
        import json
        startstring = 'var hosts = '
        start = text.find(startstring)
        if start > 0:
            start += len(startstring)
            endstring = ";\n"
            end = text.find(endstring, start)
            if end > 0:
                _LOGGER.info("Found hosts")
                self.hosts = json.loads(text[start:end])
                self.missed_host = False
                return True
        _LOGGER.error("Cannot get hosts from %s://%s",
                      self.proto, self.host)
        return False

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        try:
            return self.hosts[device.upper()]['name']
        except KeyError:
            pass
        try:
            ipv4 = self.hosts[device.upper()]['ipv4']
            if self.dns_lookup:
                try:
                    import socket
                    name = socket.gethostbyaddr(ipv4)
                    pos = name[0].find('.')
                    _LOGGER.info("resolved %s for %s(%s)",
                                 name[0], ipv4, device)
                    return name[0][0:pos]
                except socket.herror:
                    return ipv4
            else:
                return ipv4
        except KeyError:
            pass
        try:
            if self.hosts[device.upper()]['ipv6']:
                return None
        except KeyError:
            pass
        self.missed_host = True
        return None

    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False
        if self.missed_host:
            text = self.get_wireless_info()
            self.parse_hosts(text)

        url = '{}://{}/cgi-bin/luci/admin/network/wireless_status/{}'.format(
            self.proto, self.host, self.radio)
        try:
            res = self.session.get(url, verify=self.verify, timeout=5)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot retrieve json from %s://%s : %s",
                          self.proto, self.host, exception.__class__.__name__)
            return False
        if res.status_code != 200:
            _LOGGER.info("Logging in again, responsecode: %d",
                         res.status_code)
            self.login()
            return False

        try:
            result = res.json()
        except ValueError:
            _LOGGER.exception("Failed to parse response from luci")
            return False

        try:
            results = []
            for radio in result:
                for k in radio['assoclist']:
                    results.append(k)
            self.last_results = results
            return True
        except (KeyError, TypeError):
            _LOGGER.exception("No result in response from luci")
        return False


class InvalidLuciTokenError(HomeAssistantError):
    """When an invalid token is detected."""

    pass


class LuciDeviceScanner(DeviceScanner):
    """This class queries a wireless router running OpenWrt firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.verify = config[CONF_VERIFY_SSL]
        if config[CONF_SSL]:
            self.proto = 'https'
            if not self.verify and config[CONF_SSL]:
                import urllib3
                urllib3.disable_warnings(
                    urllib3.exceptions.InsecureRequestWarning)
        else:
            self.proto = 'http'
        self.last_results = {}
        self.refresh_token()
        self.mac2name = None
        self.success_init = self.token is not None

    def refresh_token(self):
        """Get a new token."""
        self.token = self.get_token()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            url = '{}://{}/cgi-bin/luci/rpc/uci'.format(self.host, self.proto)
            result = self.json_rpc(url, 'get_all', 'dhcp',
                                   params={'auth': self.token})
            if result:
                hosts = [x for x in result.values()
                         if x['.type'] == 'host' and
                         'mac' in x and 'name' in x]
                mac2name_list = [
                    (x['mac'].upper(), x['name']) for x in hosts]
                self.mac2name = dict(mac2name_list)
            else:
                # Error, handled in the json_rpc
                return
        return self.mac2name.get(device.upper(), None)

    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking ARP")

        url = '{}://{}/cgi-bin/luci/rpc/sys'.format(self.host, self.proto)

        try:
            result = self.json_rpc(url, 'net.arptable',
                                   params={'auth': self.token})
        except InvalidLuciTokenError:
            _LOGGER.info("Refreshing token")
            self.refresh_token()
            return False

        if result:
            self.last_results = []
            for device_entry in result:
                # Check if the Flags for each device contain
                # NUD_REACHABLE and if so, add it to last_results
                if int(device_entry['Flags'], 16) & 0x2:
                    self.last_results.append(device_entry['HW address'])
            return True
        return False

    # Suppressing no-self-use warning
    # pylint: disable=R0201
    def json_rpc(self, url, method, *args, **kwargs):
        """Perform one JSON RPC operation."""
        import json
        data = json.dumps({'method': method, 'params': args})
        try:
            res = requests.post(url, data=data, verify=self.verify,
                                timeout=5, **kwargs)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot connect %s://%s : %s",
                          self.proto, self.host, exception.__class__.__name__)
            return False
        if res.status_code == 200:
            try:
                result = res.json()
            except ValueError:
                # If json decoder could not parse the response
                _LOGGER.exception("Failed to parse response from luci")
                return
            try:
                return result['result']
            except KeyError:
                _LOGGER.exception("No result in response from luci")
                return
        elif res.status_code == 401:
            # Authentication error
            _LOGGER.exception(
                "Failed to authenticate, check your username and password")
            return
        elif res.status_code == 403:
            _LOGGER.error("Luci responded with a 403 Invalid token")
            raise InvalidLuciTokenError
        else:
            _LOGGER.error('Invalid response from luci: %s', res)

    def get_token(self):
        """Get authentication token for the given host+username+password."""
        url = '{}://{}/cgi-bin/luci/rpc/auth'.format(self.host, self.proto)
        return self.json_rpc(url, 'login', self.username, self.password)


def _refresh_on_access_denied(func):
    """If remove rebooted, it lost our session so rebuild one and try again."""
    def decorator(self, *args, **kwargs):
        """Wrap the function to refresh session_id on PermissionError."""
        try:
            return func(self, *args, **kwargs)
        except PermissionError:
            _LOGGER.warning("Invalid session detected." +
                            " Trying to refresh session_id and re-run RPC")
            self.session_id = self.get_session_id()
            return func(self, *args, **kwargs)
    return decorator


class UbusDeviceScanner(DeviceScanner):
    """
    This class queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.verify = config[CONF_VERIFY_SSL]
        if config[CONF_SSL]:
            self.proto = 'https'
            if not self.verify and config[CONF_SSL]:
                import urllib3
                urllib3.disable_warnings(
                    urllib3.exceptions.InsecureRequestWarning)
        else:
            proto = 'http'
        self.last_results = {}
        self.url = '{}://{}/ubus'.format(host, proto)

        self.session_id = "00000000000000000000000000000000"
        self.get_session_id()
        self.hostapd = []
        self.mac2name = None
        self.success_init = self.session_id is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def _generate_mac2name(self):
        """Must be implemented depending on the software."""
        raise NotImplementedError

    @_refresh_on_access_denied
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            self._generate_mac2name()
        name = self.mac2name.get(device.upper(), None)
        return name

    @_refresh_on_access_denied
    def _update_info(self):
        """Ensure the information from the router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking hostapd")

        if not self.hostapd:
            hostapd = self.json_rpc(
                self.url, 'list', 'hostapd.*', '')
            self.hostapd.extend(hostapd.keys())

        self.last_results = []
        results = 0
        # for each access point
        for hostapd in self.hostapd:
            result = self.json_rpc(
                self.url, 'call', hostapd, 'get_clients')

            if result:
                results = results + 1
                # Check for each device is authorized (valid wpa key)
                for key in result['clients'].keys():
                    device = result['clients'][key]
                    if device['authorized']:
                        self.last_results.append(key)

        return bool(results)

    def json_rpc(self, url, rpcmethod, subsystem, method, **params):
        """Perform one JSON RPC operation."""
        import json
        data = json.dumps({"jsonrpc": "2.0",
                           "id": 1,
                           "method": rpcmethod,
                           "params": [self.session_id,
                                      subsystem,
                                      method,
                                      params]})

        try:
            res = requests.post(url, data=data, verify=self.verify, timeout=5)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot connect %s : %s",
                          self.url, exception.__class__.__name__)
        if res.status_code == 200:
            response = res.json()
            if 'error' in response:
                if 'message' in response['error'] and \
                        response['error']['message'] == "Access denied":
                    raise PermissionError(response['error']['message'])
                else:
                    raise HomeAssistantError(response['error']['message'])
            if rpcmethod == "call":
                try:
                    return response["result"][1]
                except IndexError:
                    return
            else:
                return response["result"]

    def get_session_id(self):
        """Get the authentication token."""
        res = self.json_rpc(self.url, 'call', 'session',
                            'login', username=self.username,
                            password=self.password)
        self.session_id = res["ubus_rpc_session"]


class DnsmasqUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the dnsmasq DHCP server."""

    def __init__(self, config):
        """Initialize the scanner."""
        super(DnsmasqUbusDeviceScanner, self).__init__(config)
        self.leasefile = None

    def _generate_mac2name(self):
        if self.leasefile is None:
            result = self.json_rpc(
                self.url, 'call', 'uci', 'get',
                config="dhcp", type="dnsmasq")
            if result:
                values = result["values"].values()
                self.leasefile = next(iter(values))["leasefile"]
            else:
                return

        result = self.json_rpc(
            self.url, 'call', 'file', 'read',
            path=self.leasefile)
        if result:
            self.mac2name = dict()
            for line in result["data"].splitlines():
                hosts = line.split(" ")
                self.mac2name[hosts[1].upper()] = hosts[3]
        else:
            # Error, handled in the json_rpc
            return


class OdhcpdUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the odhcp DHCP server."""

    def _generate_mac2name(self):
        result = self.json_rpc(
            self.url, 'call', 'dhcp', 'ipv4leases')
        if result:
            self.mac2name = dict()
            for device in result["device"].values():
                for lease in device['leases']:
                    mac = lease['mac']  # mac = aabbccddeeff
                    # Convert it to expected format with colon
                    mac = ":".join(mac[i:i+2] for i in range(0, len(mac), 2))
                    self.mac2name[mac.upper()] = lease['hostname']
        else:
            # Error, handled in the _req_json_rpc
            return
