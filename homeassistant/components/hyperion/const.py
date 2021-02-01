"""Constants for Hyperion integration."""

from hyperion.const import (
    KEY_COMPONENTID_ALL,
    KEY_COMPONENTID_BLACKBORDER,
    KEY_COMPONENTID_BOBLIGHTSERVER,
    KEY_COMPONENTID_FORWARDER,
    KEY_COMPONENTID_GRABBER,
    KEY_COMPONENTID_LEDDEVICE,
    KEY_COMPONENTID_SMOOTHING,
    KEY_COMPONENTID_V4L,
)

# Maps between Hyperion API component names to Hyperion UI names. This allows Home
# Assistant to use names that match what Hyperion users may expect from the Hyperion UI.
COMPONENT_TO_NAME = {
    KEY_COMPONENTID_ALL: "All",
    KEY_COMPONENTID_SMOOTHING: "Smoothing",
    KEY_COMPONENTID_BLACKBORDER: "Blackbar Detection",
    KEY_COMPONENTID_FORWARDER: "Forwarder",
    KEY_COMPONENTID_BOBLIGHTSERVER: "Boblight Server",
    KEY_COMPONENTID_GRABBER: "Platform Capture",
    KEY_COMPONENTID_LEDDEVICE: "LED Device",
    KEY_COMPONENTID_V4L: "USB Capture",
}

CONF_AUTH_ID = "auth_id"
CONF_CREATE_TOKEN = "create_token"
CONF_INSTANCE = "instance"
CONF_INSTANCE_CLIENTS = "INSTANCE_CLIENTS"
CONF_ON_UNLOAD = "ON_UNLOAD"
CONF_PRIORITY = "priority"
CONF_ROOT_CLIENT = "ROOT_CLIENT"

DEFAULT_NAME = "Hyperion"
DEFAULT_ORIGIN = "Home Assistant"
DEFAULT_PRIORITY = 128

DOMAIN = "hyperion"

HYPERION_RELEASES_URL = "https://github.com/hyperion-project/hyperion.ng/releases"
HYPERION_VERSION_WARN_CUTOFF = "2.0.0-alpha.9"

NAME_SUFFIX_HYPERION_LIGHT = ""
NAME_SUFFIX_HYPERION_PRIORITY_LIGHT = "Priority"
NAME_SUFFIX_HYPERION_COMPONENT_SWITCH = "Component"

SIGNAL_INSTANCE_ADD = f"{DOMAIN}_instance_add_signal." "{}"
SIGNAL_INSTANCE_REMOVE = f"{DOMAIN}_instance_remove_signal." "{}"
SIGNAL_ENTITY_REMOVE = f"{DOMAIN}_entity_remove_signal." "{}"

TYPE_HYPERION_LIGHT = "hyperion_light"
TYPE_HYPERION_PRIORITY_LIGHT = "hyperion_priority_light"
TYPE_HYPERION_COMPONENT_SWITCH_BASE = "hyperion_component_switch"
