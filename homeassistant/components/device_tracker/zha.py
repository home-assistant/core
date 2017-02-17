"""
Device Trackers on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/device_tracker.zha/
"""
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

DEVICES = []


def setup_scanner(hass, config, see, discovery_info=None):
    """Setup Zigbee Home Automation device trackers."""
    if discovery_info is None:
        return

    DEVICES.append(DeviceTracker(see, **discovery_info))
    return True


class DeviceTracker:
    """ZHA device which reports when it is seen to device_tracker."""

    def __init__(self, see, endpoint, **kwargs):
        """Initialize ZHA device_tracker device."""
        self._mac = str(endpoint.device.ieee)
        self.see = see
        endpoint.add_listener(self)

    def unknown_cluster_message(self, *args, **kwargs):
        """Handle messages received for an unknown cluster."""
        self.see(mac=self._mac, source_type=SOURCE_TYPE_ROUTER)
