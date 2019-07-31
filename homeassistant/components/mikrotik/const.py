"""Constants used in the Mikrotik components."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR, DEVICE_CLASS_CONNECTIVITY)
from homeassistant.components.sensor import DOMAIN as SENSOR

MIKROTIK = 'mikrotik'
CLIENT = 'mikrotik_client'

MTK_DEFAULT_WAN = 'ether1'

CONF_ARP_PING = 'arp_ping'
CONF_WAN_PORT = 'wan_port'
CONF_TRACK_DEVICES = 'track_devices'
CONF_LOGIN_METHOD = 'login_method'
CONF_ENCODING = 'encoding'
DEFAULT_ENCODING = 'utf-8'

CONNECTING = 'connected'
CONNECTED = 'connected'

IDENTITY = 'identity'
ARP = 'arp'
DHCP = 'dhcp'
WIRELESS = 'wireless'
CAPSMAN = 'capsman'

MEGA = 1048576

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
