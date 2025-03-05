"""Constants for the Govee light local integration."""

from datetime import timedelta

DOMAIN = "govee_light_local"
MANUFACTURER = "Govee"

CONF_MULTICAST_ADDRESS_DEFAULT = "239.255.255.250"
CONF_TARGET_PORT_DEFAULT = 4001
CONF_LISTENING_PORT_DEFAULT = 4002
CONF_DISCOVERY_INTERVAL_DEFAULT = 60

SCAN_INTERVAL = timedelta(seconds=30)
DISCOVERY_TIMEOUT = 5

CONF_AUTO_DISCOVERY = "auto_discovery"
CONF_MANUAL_DEVICES = "manual_devices"
CONF_DEVICE_IP = "device_ip"
CONF_IPS_TO_REMOVE = "ips_to_remove"


SIGNAL_GOVEE_DEVICE_REMOVE = "govee_local_govee_device_remove"
