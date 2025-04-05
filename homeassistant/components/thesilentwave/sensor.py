"""Support for TheSilentWave sensors."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor from a config entry."""
    coordinator = hass.data["thesilentwave"][entry.entry_id]
    async_add_entities([TheSilentWaveSensor(coordinator, entry.entry_id)], True)


class TheSilentWaveSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TheSilentWave sensor."""

    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"silent_wave_{entry_id}"
        self._attr_name = coordinator.name
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_should_poll = True

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={("thesilentwave", self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="TheSilentWave",
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:power" if self.state == "on" else "mdi:power-off"
