"""Consts for Cast integration."""

DOMAIN = "cast"

# Stores a threading.Lock that is held by the internal pychromecast discovery.
INTERNAL_DISCOVERY_RUNNING_KEY = "cast_discovery_running"
# Stores UUIDs of cast devices that were added as entities. Doesn't store
# None UUIDs.
ADDED_CAST_DEVICES_KEY = "cast_added_cast_devices"
# Stores an audio group manager.
CAST_MULTIZONE_MANAGER_KEY = "cast_multizone_manager"
# Store a CastBrowser
CAST_BROWSER_KEY = "cast_browser"

# Dispatcher signal fired with a ChromecastInfo every time we discover a new
# Chromecast or receive it through configuration
SIGNAL_CAST_DISCOVERED = "cast_discovered"

# Dispatcher signal fired with a ChromecastInfo every time a Chromecast is
# removed
SIGNAL_CAST_REMOVED = "cast_removed"

# Dispatcher signal fired when a Chromecast should show a Home Assistant Cast view.
SIGNAL_HASS_CAST_SHOW_VIEW = "cast_show_view"

CONF_IGNORE_CEC = "ignore_cec"
CONF_KNOWN_HOSTS = "known_hosts"
