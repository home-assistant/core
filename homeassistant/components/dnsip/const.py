"""Constants for dnsip integration."""

from homeassistant.const import Platform

DOMAIN = "dnsip"
PLATFORMS = [Platform.SENSOR]

CONF_HOSTNAME = "hostname"
CONF_RESOLVER = "resolver"
CONF_RESOLVER_IPV6 = "resolver_ipv6"
CONF_PORT_IPV6 = "port_ipv6"
CONF_IPV4 = "ipv4"
CONF_IPV6 = "ipv6"
CONF_IPV6_V4 = "ipv6_v4"

DEFAULT_HOSTNAME = "myip.opendns.com"
DEFAULT_IPV6 = False
DEFAULT_NAME = "myip"
DEFAULT_RESOLVER = "208.67.222.222"
DEFAULT_PORT = 53
DEFAULT_RESOLVER_IPV6 = "2620:119:53::53"
