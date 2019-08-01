"""Constants used in the Mikrotik components."""

MIKROTIK = 'mikrotik'
MIKROTIK_DOMAIN = MIKROTIK
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

ARP = 'arp'
DHCP = 'dhcp'
WIRELESS = 'wireless'
CAPSMAN = 'capsman'
IDENTITY = 'identity'

MIKROTIK_SERVICES = {
    IDENTITY: '/system/identity/getall',
    ARP: '/ip/arp/getall',
    DHCP: '/ip/dhcp-server/lease/getall',
    WIRELESS: '/interface/wireless/registration-table/getall',
    CAPSMAN: '/caps-man/registration-table/getall'
}

ATTRIB_DEVICE_TRACKER = ['mac-address', 'rx-signal', 'ssid', 'interface',
                         'comment', 'host-name', 'address', 'uptime',
                         'rx-rate', 'tx-rate', 'last-seen']
