"""Control binary sensor instances."""

from ProgettiHWSW.input import Input

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import setup_input
from .const import DOMAIN


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set the progettihwsw platform up and create sensor instances (legacy)."""

    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the binary sensors from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    input_count = config_entry.data["input_count"]
    binary_sensors = []

    for i in range(1, int(input_count)):
        binary_sensors.append(
            ProgettihwswBinarySensor(
                hass, config_entry, f"Input #{i}", setup_input(board_api, i)
            )
        )

    async_add_entities(binary_sensors, True)


class ProgettihwswBinarySensor(BinarySensorEntity):
    """Represent a binary sensor."""

    def __init__(self, hass, config_entry, name, sensor: Input):
        """Set initializing values."""
        self._name = name
        self._sensor = sensor
        self._state = None

    def added_to_hass(self):
        """Run this function when entity is added to HASS."""

        def setup_entity():
            """Set up sensor entity when HA starts up."""
            self._sensor.update()
            self._state = self._sensor.is_on
            self.schedule_update_ha_state(True)

        self.hass.add_executor_job(setup_entity)

    @property
    def should_poll(self):
        """Poll for new switch state."""
        return True

    @property
    def name(self):
        """Return the sensor name."""
        return self._name

    @property
    def is_on(self):
        """Get sensor state."""
        return self._state

    async def async_update(self):
        """Update the state of binary sensor."""
        self.hass.async_add_executor_job(self._sensor.update)
        self._state = self._sensor.is_on
