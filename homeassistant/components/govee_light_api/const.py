"""Constants for the Govee Lights - Local API integration."""

from datetime import timedelta

DOMAIN = "govee_light_api"
MANUFACTURER = "Govee"

CONF_MULTICAST_ADDRESS_DEFAULT = "239.255.255.250"
CONF_TARGET_PORT_DEFAULT = 4001
CONF_LISENING_PORT_DEFAULT = 4002
CONF_DISCOVERY_INTERVAL_DEFAULT = 60

DISPATCH_GOVEE_LIGHT_DISCOVERED = "govee_light_discovered"
SCAN_INTERVAL = timedelta(seconds=30)
