"""Constants for the OpenWrt (ubus) integration."""

DOMAIN = "ubus"

CONF_DHCP_SOFTWARE = "dhcp_software"
DEFAULT_DHCP_SOFTWARE = "dnsmasq"
DHCP_SOFTWARES = ["dnsmasq", "odhcpd", "none"]
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

SIGNAL_CLIENTS_UPDATED = f"{DOMAIN}_clients_updated"
