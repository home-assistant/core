"""Summary binary data from Uptime Kuma."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN]
    # print(coordinator.data)
    async_add_entities(
        UptimeKumaBinarySensor(coordinator, monitor) for monitor in coordinator.data
    )


class UptimeKumaBinarySensor(BinarySensorEntity, CoordinatorEntity):
    """Represents an Uptime Kuma binary sensor."""

    def __init__(self, coordinator, monitor):
        """Initialize the Uptime Kuma binary sensor."""
        super().__init__(coordinator)
        self._name = monitor

    @property
    def icon(self):
        """Return the icon for this binary sensor."""
        return "mdi:cloud"

    @property
    def name(self):
        """Return the name for this binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.coordinator.data[self._name]["monitor_status"] == 1.0
