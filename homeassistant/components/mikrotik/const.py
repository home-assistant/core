"""Constants used in the Mikrotik components."""

DOMAIN = 'mikrotik'
MIKROTIK = DOMAIN
CLIENT = 'mikrotik_client'

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

MIKROTIK_SERVICES = {
    IDENTITY: '/system/identity/getall',
    ARP: '/ip/arp/getall',
    DHCP: '/ip/dhcp-server/lease/getall',
    WIRELESS: '/interface/wireless/registration-table/getall',
    CAPSMAN: '/caps-man/registration-table/getall'
}

ATTR_DEVICE_TRACKER = ['mac-address', 'rx-signal', 'ssid', 'interface',
                         'comment', 'host-name', 'address', 'uptime',
                         'rx-rate', 'tx-rate', 'last-seen']
