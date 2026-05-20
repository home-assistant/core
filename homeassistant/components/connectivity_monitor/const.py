"""Constants for the Connectivity Monitor integration."""

import json
import os

DOMAIN = "connectivity_monitor"

# Load version from manifest.json
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "manifest.json")
try:
    with open(MANIFEST_PATH, encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
        VERSION = manifest.get("version", "0.0.0")
except OSError, ValueError, KeyError:
    VERSION = "0.0.0"

DEFAULT_PORT = 80
DEFAULT_PROTOCOL = "TCP"
DEFAULT_INTERVAL = 300
DEFAULT_PING_TIMEOUT = 2
DEFAULT_DNS_SERVER = "1.1.1.1"
DEFAULT_ALERT_DELAY = 15
DEFAULT_ALERT_GROUP = None

CONF_HOST = "host"
CONF_PROTOCOL = "protocol"
CONF_PORT = "port"
CONF_INTERVAL = "interval"
CONF_TARGETS = "targets"
CONF_DNS_SERVER = "dns_server"
CONF_ALERT_GROUP = "alert_group"
CONF_ALERT_DELAY = "alert_delay"
CONF_ALERTS_ENABLED = "alerts_enabled"
CONF_ALERT_ACTION_ENABLED = "alert_action_enabled"
CONF_ALERT_ACTION = "alert_action"
CONF_ALERT_ACTION_DELAY = "alert_action_delay"
DEFAULT_ALERT_ACTION_DELAY = 30

PROTOCOL_TCP = "TCP"
PROTOCOL_UDP = "UDP"
PROTOCOL_ICMP = "ICMP"
PROTOCOL_AD_DC = "AD_DC"
PROTOCOL_ZHA = "ZHA"
PROTOCOL_MATTER = "MATTER"
PROTOCOL_ESPHOME = "ESPHOME"
PROTOCOL_BLUETOOTH = "BLUETOOTH"

NON_NETWORK_PROTOCOLS = (
    PROTOCOL_ZHA,
    PROTOCOL_MATTER,
    PROTOCOL_ESPHOME,
    PROTOCOL_BLUETOOTH,
)

PROTOCOLS = [PROTOCOL_TCP, PROTOCOL_UDP, PROTOCOL_ICMP, PROTOCOL_AD_DC]
# ZHA / ZigBee device monitoring
CONF_ZHA_IEEE = "ieee"
CONF_INACTIVE_TIMEOUT = "inactive_timeout"
DEFAULT_INACTIVE_TIMEOUT = 60  # minutes

# Matter device monitoring
CONF_MATTER_NODE_ID = "matter_node_id"

# ESPHome device monitoring
CONF_ESPHOME_DEVICE_ID = "esphome_device_id"

# Bluetooth device monitoring
CONF_BLUETOOTH_ADDRESS = "bt_address"

# Default Active Directory ports
AD_DC_PORTS = {
    88: "Kerberos",
    139: "NetBIOS",
    389: "LDAP",
    445: "SMB",
    464: "Kerberos Password Change",
    636: "LDAPS",
    3268: "Global Catalog",
    3269: "Global Catalog SSL",
}
