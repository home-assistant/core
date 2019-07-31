"""The mikrotik component."""
import logging
import ssl
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT,
    CONF_SSL, CONF_METHOD, CONF_SENSORS, CONF_BINARY_SENSORS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util import slugify
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER)
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR, DEVICE_CLASS_CONNECTIVITY)

_LOGGER = logging.getLogger(__name__)

NAME = 'Mikrotik'
DOMAIN = 'mikrotik'
MIKROTIK = DOMAIN
CLIENT = 'mikrotik_client'

CONF_ARP_PING = 'arp_ping'
CONF_WAN_PORT = 'wan_port'
CONF_TRACK_DEVICES = 'track_devices'
CONF_LOGIN_METHOD = 'login_method'
CONF_ENCODING = 'encoding'
DEFAULT_ENCODING = 'utf-8'

CONNECTING = 'connected'
CONNECTED = 'connected'

MTK_DEFAULT_WAN = 'ether1'
MTK_DEFAULT_API_PORT = '8728'
MTK_DEFAULT_API_SSL_PORT = '8729'
MTK_LOGIN_PLAIN = 'plain'
MTK_LOGIN_TOKEN = 'token'

IDENTITY = 'identity'
ARP = 'arp'
DHCP = 'dhcp'
WIRELESS = 'wireless'
CAPSMAN = 'capsman'

MIKROTIK_SERVICES = {
    IDENTITY: '/system/identity/getall',
    ARP: '/ip/arp/getall',
    DHCP: '/ip/dhcp-server/lease/getall',
    WIRELESS: '/interface/wireless/registration-table/getall',
    CAPSMAN: '/caps-man/registration-table/getall'
}

SENSOR_SYSINFO = 'sysinfo'
SENSOR_CPU = 'cpu'
SENSOR_MEMORY = 'memory'
SENSOR_DISK = 'disk'
SENSOR_DOWNLOAD_SPEED = 'download_speed'
SENSOR_UPLOAD_SPEED = 'upload_speed'

ATTRIB_SYSINFO = ['board-name', 'serial-number',
                  'version', 'factory-firmware',
                  'firmware-type', 'current-firmware',
                  'upgrade-frimware', 'routerboard',
                  'cpu', 'total-memory',
                  'architecture-name']
ATTRIB_CPU = ['cpu',
              'cpu-frequency',
              'cpu-count']
ATTRIB_MEMORY = ['free-memory',
                 'total-memory']
ATTRIB_DISK = ['free-hdd-space',
               'total-hdd-space']
ATTRIB_DOWNLOAD_SPEED = ['name',
                         'rx-packets-per-second',
                         'rx-bits-per-second',
                         'fp-rx-packets-per-second',
                         'fp-rx-bits-per-second',
                         'rx-drops-per-second',
                         'rx-errors-per-second']
ATTRIB_UPLOAD_SPEED = ['name',
                       'tx-packets-per-second',
                       'tx-bits-per-second',
                       'fp-tx-packets-per-second',
                       'fp-tx-bits-per-second',
                       'tx-drops-per-second',
                       'tx-queue-drops-per-second',
                       'tx-errors-per-second']
ATTRIB_DOWNLOAD = ['name', 'tx-bytes']
ATTRIB_UPLOAD = ['name', 'rx-bytes']

PARAM_SPEED = {'interface': MTK_DEFAULT_WAN,
               'duration': '1s'}
MEGA = 1048576

# Sensor types are defined like:
# Name, units, icon, state item, api cmd(s), attributes
SENSORS = {
    SENSOR_SYSINFO: ['System Info', None, 'mdi:switch',
                     'board-name',
                     ['/system/routerboard/getall',
                      '/system/resource/getall'],
                     ATTRIB_SYSINFO, None, None],
    SENSOR_CPU: ['CPU Load', '%', 'mdi:chip',
                 'cpu-load',
                 ['/system/resource/getall'],
                 ATTRIB_CPU, None],
    SENSOR_MEMORY: ['Memory Free', 'Mbytes',
                    'mdi:memory', 'free-memory',
                    ['/system/resource/getall'],
                    ATTRIB_MEMORY, None],
    SENSOR_DISK: ['Disk Free', 'Mbytes', 'mdi:harddisk',
                  'free-hdd-space',
                  ['/system/resource/getall'],
                  ATTRIB_DISK, None],
    SENSOR_DOWNLOAD_SPEED: ['Download Speed', 'Mbps',
                            'mdi:download-network',
                            'rx-bits-per-second',
                            ['/interface/monitor-traffic'],
                            ATTRIB_DOWNLOAD_SPEED,
                            PARAM_SPEED],
    SENSOR_UPLOAD_SPEED: ['Upload Speed', 'Mbps',
                          'mdi:upload-network',
                          'tx-bits-per-second',
                          ['/interface/monitor-traffic'],
                          ATTRIB_UPLOAD_SPEED, PARAM_SPEED],
}

BINARY_SENSOR_NETWATCH = 'netwatch'
BINARY_SENSOR_INTERNET = 'internet'
ATTRIB_NETWATCH = ['host', 'interval',
                   'timeout', 'since', 'disabled', 'comment']
ATTRIB_INTERNET = ['name', 'cloud-rtt', 'state-change-time']

# Binary Sensors: Name, Class, icon, state, api cmd, attributes, state hash
BINARY_SENSORS = {
    BINARY_SENSOR_NETWATCH: ['Netwatch', DEVICE_CLASS_CONNECTIVITY,
                             'mdi:lan-connect', '/tool/netwatch/getall',
                             'status', ATTRIB_NETWATCH,
                             {'up': True, 'down': False},
                             'host'],
    BINARY_SENSOR_INTERNET: ['Internet', DEVICE_CLASS_CONNECTIVITY,
                             'mdi:wan',
                             '/interface/detect-internet/state/getall',
                             'state',
                             ATTRIB_INTERNET,
                             {'internet': True, 'unknown': False},
                             'name'],
}

ATTRIB_DEVICE_TRACKER = ['mac-address', 'rx-signal', 'ssid', 'interface',
                         'comment', 'host-name', 'address', 'uptime',
                         'rx-rate', 'tx-rate', 'last-seen']

MIKROTIK_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_METHOD): cv.string,
        vol.Optional(CONF_LOGIN_METHOD):
            vol.Any(MTK_LOGIN_PLAIN, MTK_LOGIN_TOKEN),
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_TRACK_DEVICES, default=True): cv.boolean,
        vol.Optional(CONF_ARP_PING, default=False): cv.boolean,
        vol.Optional(CONF_SENSORS): vol.All(
            cv.ensure_list, [vol.In(SENSORS)]),
        vol.Optional(CONF_BINARY_SENSORS):
            vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
        vol.Optional(CONF_WAN_PORT, default=MTK_DEFAULT_WAN): cv.string,
    })
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [MIKROTIK_SCHEMA])
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Mikrotik component."""
    hass.data[MIKROTIK] = {}
    hass.data[CLIENT] = MikrotikAPI(hass, config[DOMAIN])

    for device in config[DOMAIN]:
        host = device[CONF_HOST]
        hass.data[MIKROTIK][host] = {}
        hass.data[CLIENT].connect_to_device(host)

        _LOGGER.debug("[%s] Loading Mikrotik device intrgrations.", host)

        sensors = device.get(CONF_SENSORS)
        if sensors:
            hass.async_create_task(
                async_load_platform(
                    hass, SENSOR, DOMAIN, device, config))

        binary_sensors = device.get(CONF_BINARY_SENSORS)
        if binary_sensors:
            hass.async_create_task(
                async_load_platform(
                    hass, BINARY_SENSOR, DOMAIN, {
                        CONF_BINARY_SENSORS: binary_sensors,
                        CONF_HOST: host
                    }, config))

        if device[CONF_TRACK_DEVICES]:
            hass.data[MIKROTIK][ARP] = {}
            hass.data[MIKROTIK][DHCP] = {}
            hass.async_create_task(
                async_load_platform(
                    hass, DEVICE_TRACKER, DOMAIN, device, config))

    return True


class MikrotikAPI:
    """Handle all communication with the Mikrotik API."""

    def __init__(self, hass, configs):
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config = {}
        self._client = {}
        self._hosts = {}
        for config in configs:
            host = config.get(CONF_HOST)
            self._hosts[host] = {}
            self._hosts[host]['config'] = config
            self._hosts[host][CONNECTED] = False
            self._hosts[host][CONNECTING] = False
            self._hosts[host]['kwargs'] = None
            self._hosts[host][CONF_WAN_PORT] = config.get(CONF_WAN_PORT)
            self._hosts[host][DEVICE_TRACKER] = None
            self._hosts[host][CONF_ARP_PING] = config.get(CONF_ARP_PING)

    def config_kwargs(self, config):
        """Build Mikrotik host config."""
        from librouteros.login import login_plain, login_token
        login = config.get(CONF_LOGIN_METHOD)
        if login == MTK_LOGIN_PLAIN:
            login_method = (login_plain,)
        elif login == MTK_LOGIN_TOKEN:
            login_method = (login_token,)
        else:
            login_method = (login_plain, login_token)

        kwargs = {
            'encoding': config[CONF_ENCODING],
            'login_methods': login_method
        }

        if CONF_PORT in config:
            kwargs['port'] = config[CONF_PORT]
        else:
            kwargs['port'] = MTK_DEFAULT_API_PORT

        if config[CONF_SSL]:
            if CONF_PORT not in config:
                kwargs['port'] = MTK_DEFAULT_API_SSL_PORT
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            kwargs['ssl_wrapper'] = ssl_context.wrap_socket
        self._hosts[host]['kwargs'] = kwargs
        return

    def get_polling_method(self, host):
        """Get Mikrotik device_tracker polling method."""
        import librouteros
        polling_method = self._hosts[host]['config'].get(CONF_METHOD)
        try:
            capsman_exist = self._client[host](
                cmd=MIKROTIK_SERVICES[CAPSMAN])
        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError):
            _LOGGER.info("Mikrotik %s: Not a CAPsMAN controller. Trying "
                         "local wireless interfaces.", (host))
            capsman_exist = False
        try:
            wireless_exist = self._client[host](
                cmd=MIKROTIK_SERVICES[WIRELESS])
        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError):
            wireless_exist = False

        if not wireless_exist and not capsman_exist \
                or polling_method == 'ip':
            _LOGGER.info(
                "Mikrotik %s: Wireless adapters not found. Try to "
                "use DHCP lease table as presence tracker source. "
                "Please decrease lease time as much as possible",
                host)
        if polling_method:
            _LOGGER.info("Mikrotik %s: Manually selected polling method %s",
                         host, polling_method)
            device_tracker = polling_method
        else:
            if capsman_exist:
                device_tracker = CAPSMAN
            elif wireless_exist:
                device_tracker = WIRELESS
            else:
                device_tracker = DHCP
            _LOGGER.info("Mikrotik %s: Using device_tracker method %s",
                         host, device_tracker)
        self._hosts[host][DEVICE_TRACKER] = device_tracker

    def connect_to_device(self, host):
        """Connect to Mikrotik method."""
        import librouteros
        import time
        tick = 0
        while self._hosts[host][CONNECTING] and tick < 60:
            time.sleep(1)
            tick += 1
        if self._hosts[host][CONNECTED]:
            return
        self._hosts[host][CONNECTING] = True
        self._hosts[host][CONNECTED] = False
        _LOGGER.debug("[%s] Connecting to Mikrotik device.", host)
        config = self._hosts[host]['config']
        self.config_kwargs(config)
        try:
            self._client[host] = librouteros.connect(
                config[CONF_HOST], config[CONF_USERNAME],
                config.get(CONF_PASSWORD, ''),
                **self._hosts[host]['kwargs'])
        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error(
                "Mikrotik error for device %s. ",
                "Connection error: %s", host, api_error)
            self._hosts[host][CONNECTING] = False
            self._hosts[host][CONNECTED] = False
            self._client[host] = None
            return False

        host_name = (self._client[host](
            cmd=MIKROTIK_SERVICES[IDENTITY]))[0]['name']
        if not host_name:
            _LOGGER.error("Mikrotik failed to connect to %s.", host)
            return False
        self.hass.data[MIKROTIK][host]['name'] = host_name
        _LOGGER.info("Mikrotik Connected to %s (%s).", host_name, host)
        self._hosts[host][CONNECTING] = False
        self._hosts[host][CONNECTED] = True
        return True

    def arp_ping(self, host, mac, interface):
        """Attempt to arp ping MAC address via interface."""
        params = {'arp-ping': 'yes', 'interval': '100ms', 'count': 3,
                  'interface': interface, 'address': mac}
        cmd = '/ping'
        data = self._client[host](cmd, params)
        status = 0
        for result in data:
            if 'status' in result:
                status += 1
        if status == len(data):
            return False
        return data

    async def update_info(self, host):
        """Update info from Mikrotik API."""
        _LOGGER.debug("[%s] Updating Mikrotik info.", host)
        if not self._hosts[host][CONNECTED]:
            self.connect_to_device(host)
        data = self.get_api(host, '/system/routerboard/getall')
        if data is None:
            _LOGGER.error(
                "Mikrotik update_info. Device %s is not connected.",
                host)
            self._hosts[host][CONNECTED] = False
            return
        self.hass.data[MIKROTIK][host]['info'] = data[0]

    async def update_device_tracker(self, host):
        """Update device_tracker from Mikrotik API."""
        self.hass.data[MIKROTIK][host][DEVICE_TRACKER] = {}
        host_data = self.hass.data[MIKROTIK][host]
        host_name = host_data.get('name')

        if self._hosts[host][DEVICE_TRACKER] is None:
            self.get_polling_method(host)
        method = self._hosts[host][DEVICE_TRACKER]
        _LOGGER.debug(
            "[%s] Updating Mikrotik device_tracker using %s.",
            host, method)
        data = self.get_api(host, MIKROTIK_SERVICES[method])
        if data is None:
            self.update_info(host)
            return

        arp = self.get_api(host, MIKROTIK_SERVICES[ARP])
        for result in arp:
            if 'mac-address' in result and result['invalid'] is False:
                self.hass.data[MIKROTIK][ARP][
                    result['mac-address']] = result

        for device in data:
            mac = device['mac-address']
            if method == DHCP:
                if 'active-address' not in device:
                    continue
                self.hass.data[MIKROTIK][DHCP][mac] = data
                if (self._hosts[host][CONF_ARP_PING] and
                        mac in self.hass.data[MIKROTIK][ARP]):
                    interface = self.hass.data[MIKROTIK][
                        ARP][mac]['interface']
                    if not self.arp_ping(host, mac, interface):
                        continue
            attributes = {}
            for attrib in ATTRIB_DEVICE_TRACKER:
                if attrib in device:
                    attributes[slugify(attrib)] = device[attrib]
            attributes['source_type'] = 'router'
            attributes['scanner_type'] = method
            attributes['scanner_host'] = host
            attributes['scanner_host_name'] = host_name
            if mac in self.hass.data[MIKROTIK][ARP]:
                attributes['ip_address'] = self.hass.data[MIKROTIK][
                    ARP][mac]['address']
            if mac in self.hass.data[MIKROTIK][DHCP]:
                attributes['host_name'] = self.hass.data[MIKROTIK][
                    DHCP][mac]['host-name']
            self.hass.data[MIKROTIK][host][
                DEVICE_TRACKER][mac] = attributes

    async def update_sensors(self, host, sensor_type):
        """Update sensors from Mikrotik API."""
        _LOGGER.debug("[%s] Updating Mikrotik sensor %s.",
                      host, sensor_type)
        results = {}
        self.hass.data[MIKROTIK][host][SENSOR][sensor_type] = None
        params = SENSORS[sensor_type][6]
        if params and 'interface' in params:
            params['interface'] = self._hosts[host][CONF_WAN_PORT]

        for cmd in SENSORS[sensor_type][4]:
            data = self.get_api(host, cmd, params)
            if data is None:
                self.update_info(host)
                return
            results.update(data[0])
        sensor = {}
        sensor['state'] = None
        sensor['attrib'] = {}

        for key in results:
            if key == SENSORS[sensor_type][3]:
                sensor['state'] = results[key]
            if key in SENSORS[sensor_type][5]:
                sensor['attrib'][slugify(key)] = results[key]

        sensor_unit = SENSORS[sensor_type][1]
        if sensor_unit and sensor['state']:
            if any(unit in sensor_unit for unit in ['bit', 'byte', 'bps']):
                sensor['state'] = format(
                    (float(sensor['state']) / MEGA), '.2f')

        self.hass.data[MIKROTIK][host][SENSOR][sensor_type] = sensor

    async def update_binary_sensor(self, host, sensor_type, index=None):
        """Update binary sensors from Mikrotik API"""
        _LOGGER.debug("[%s] Updating Mikrotik binary_sensor %s.",
                      host, sensor_type)
        cmd = BINARY_SENSORS[sensor_type][3]
        data = self.get_api(host, cmd)
        if data is None:
            self.update_info(host)
            return
        binary_sensors = {}
        self.hass.data[MIKROTIK][host][sensor_type]['count'] = len(data)
        states = BINARY_SENSORS[sensor_type][6]
        for index, result in enumerate(data):
            binary_sensors[index] = {}
            binary_sensors[index]['attrib'] = {}
            binary_sensors[index]['state'] = None
            for key in result:
                if key == BINARY_SENSORS[sensor_type][4]:
                    binary_sensors[index]['state'] = states[result[key]]
                if key in BINARY_SENSORS[sensor_type][5]:
                    binary_sensors[index]['attrib'][
                        slugify(key)] = result[key]

        self.hass.data[MIKROTIK][host][
            CONF_BINARY_SENSORS][sensor_type] = binary_sensors

    def get_api(self, host, api_cmd, params=None):
        """Retrieve data from Mikrotik API."""
        import librouteros
        if not self._client[host] or not self._hosts[host][CONNECTED]:
            if not self.connect_to_device(host):
                return None
        try:
            if params:
                response = self._client[host](cmd=api_cmd, **params)
            else:
                response = self._client[host](cmd=api_cmd)
        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error(
                "Failed to retrieve data from mikrotik device. "
                "%s cmd=[%s] Error: %s", host, api_cmd, api_error)
            self._hosts[host][CONNECTED] = False
            return None
        return response
