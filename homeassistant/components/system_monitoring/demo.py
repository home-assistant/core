"""
Demo platform that offers fake system monitoring details.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.system_monitoring import SystemMonitoring


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo system monitoring resources."""
    add_devices([
        DemoSystemMonitoring(None, 'cpu_speed', 1.3),
        DemoSystemMonitoring('Server', 'load_15m', 0.6),
    ])


class DemoSystemMonitoring(SystemMonitoring):
    """Representation of a system monitoring resource."""

    def __init__(self, system, resource, value):
        """Initialize the Demo system monitoring resource."""
        self._resource = resource
        self._system = system
        self._value = value

    @property
    def should_poll(self):
        """No polling needed for a demo resource."""
        return False

    @property
    def system(self):
        """Return the name of the monitored system."""
        return self._system

    @property
    def resource(self):
        """Return the name of the resource."""
        return self._resource

    @property
    def value(self):
        """Return the value of the resource."""
        return self._value
