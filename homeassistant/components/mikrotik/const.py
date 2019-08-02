"""Constants used in the Mikrotik components."""

DOMAIN = 'mikrotik'
MIKROTIK = DOMAIN
CLIENT = 'mikrotik_client'

SENSOR = 'sensor'

MTK_DEFAULT_WAN = 'ether1'
MTK_LOGIN_PLAIN = 'plain'
MTK_LOGIN_TOKEN = 'token'

CONF_ARP_PING = 'arp_ping'
CONF_WAN_PORT = 'wan_port'
CONF_TRACK_DEVICES = 'track_devices'
CONF_LOGIN_METHOD = 'login_method'
CONF_ENCODING = 'encoding'
DEFAULT_ENCODING = 'utf-8'

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

ATTR_SYSINFO = ['board-name', 'serial-number',
                  'version', 'factory-firmware',
                  'firmware-type', 'current-firmware',
                  'upgrade-frimware', 'routerboard',
                  'cpu', 'total-memory',
                  'architecture-name']
ATTR_CPU = ['cpu',
              'cpu-frequency',
              'cpu-count']
ATTR_MEMORY = ['free-memory',
                 'total-memory']
ATTR_DISK = ['free-hdd-space',
               'total-hdd-space']
ATTR_DOWNLOAD_SPEED = ['name',
                         'rx-packets-per-second',
                         'rx-bits-per-second',
                         'fp-rx-packets-per-second',
                         'fp-rx-bits-per-second',
                         'rx-drops-per-second',
                         'rx-errors-per-second']
ATTR_UPLOAD_SPEED = ['name',
                       'tx-packets-per-second',
                       'tx-bits-per-second',
                       'fp-tx-packets-per-second',
                       'fp-tx-bits-per-second',
                       'tx-drops-per-second',
                       'tx-queue-drops-per-second',
                       'tx-errors-per-second']
ATTR_DOWNLOAD = ['name', 'tx-bytes']
ATTR_UPLOAD = ['name', 'rx-bytes']

PARAM_SPEED = {'interface': MTK_DEFAULT_WAN,
               'duration': '1s'}

# Sensor types are defined like:
# Name, units, icon, state item, api cmd(s), attributes, API parameters
SENSORS = {
    SENSOR_SYSINFO: ['System Info', None, 'mdi:switch',
                     'board-name',
                     ['/system/routerboard/getall',
                      '/system/resource/getall'],
                     ATTR_SYSINFO, None, None],
    SENSOR_CPU: ['CPU Load', '%', 'mdi:chip',
                 'cpu-load',
                 ['/system/resource/getall'],
                 ATTR_CPU, None],
    SENSOR_MEMORY: ['Memory Free', 'Mbytes',
                    'mdi:memory', 'free-memory',
                    ['/system/resource/getall'],
                    ATTR_MEMORY, None],
    SENSOR_DISK: ['Disk Free', 'Mbytes', 'mdi:harddisk',
                  'free-hdd-space',
                  ['/system/resource/getall'],
                  ATTR_DISK, None],
    SENSOR_DOWNLOAD_SPEED: ['Download Speed', 'Mbps',
                            'mdi:download-network',
                            'rx-bits-per-second',
                            ['/interface/monitor-traffic'],
                            ATTR_DOWNLOAD_SPEED,
                            PARAM_SPEED],
    SENSOR_UPLOAD_SPEED: ['Upload Speed', 'Mbps',
                          'mdi:upload-network',
                          'tx-bits-per-second',
                          ['/interface/monitor-traffic'],
                          ATTR_UPLOAD_SPEED, PARAM_SPEED],
}

ATTR_DEVICE_TRACKER = ['mac-address', 'rx-signal', 'ssid', 'interface',
                         'comment', 'host-name', 'address', 'uptime',
                         'rx-rate', 'tx-rate', 'last-seen']
