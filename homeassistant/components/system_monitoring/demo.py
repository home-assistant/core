"""
Demo platform that offers fake system monitoring details.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.system_monitoring import SystemMonitoring
from homeassistant.components.system_monitoring.const import (
    FREQUENCY_MHZ, SIZE_GB)
from homeassistant.components.system_monitoring import unit_registry


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo system monitoring resources."""
    add_devices([
        DemoSystemMonitoring(None, 'cpu_speed', 1300, FREQUENCY_MHZ),
        DemoSystemMonitoring('Server', 'load_15m', 0.6, None),
        DemoSystemMonitoring('Desktop', 'disk_use', 900, SIZE_GB),
    ])


class DemoSystemMonitoring(SystemMonitoring):
    """Representation of a system monitoring resource."""

    def __init__(self, system, resource, value, source_unit):
        """Initialize the Demo system monitoring resource."""
        self._resource = resource
        self._system = system
        self._source_unit = source_unit
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
        return self._value * unit_registry(self._source_unit)
