"""The Nmap Tracker integration."""

from typing import TYPE_CHECKING, Final

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import NmapTrackedDevices

DOMAIN: Final = "nmap_tracker"

PLATFORMS: Final = [Platform.DEVICE_TRACKER]

# Tracked devices are keyed by MAC across every config entry, so the registry
# is shared rather than owned by any one entry.
NMAP_TRACKED_DEVICES: HassKey[NmapTrackedDevices] = HassKey("nmap_tracked_devices")

# Interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL: Final = "home_interval"
CONF_OPTIONS: Final = "scan_options"
CONF_HOSTS_LIST: Final = "hosts_list"
CONF_HOSTS_EXCLUDE: Final = "hosts_exclude"
CONF_MAC_EXCLUDE: Final = "mac_exclude"
DEFAULT_OPTIONS: Final = "-n -sn -PR -T4 --min-rate 10 --host-timeout 5s"

TRACKER_SCAN_INTERVAL: Final = 120
