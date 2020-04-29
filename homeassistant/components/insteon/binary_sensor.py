"""Support for INSTEON dimmers via PowerLinc Modem."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from .insteon_entity import InsteonEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "openClosedSensor": "opening",
    "ioLincSensor": "opening",
    "motionSensor": "motion",
    "doorSensor": "door",
    "wetLeakSensor": "moisture",
    "lightSensor": "light",
    "batterySensor": "battery",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the INSTEON device class for the hass platform."""
    insteon_modem = hass.data["insteon"].get("modem")

    address = discovery_info["address"]
    device = insteon_modem.devices[address]
    state_key = discovery_info["state_key"]
    name = device.states[state_key].name
    if name != "dryLeakSensor":
        _LOGGER.debug(
            "Adding device %s entity %s to Binary Sensor platform",
            device.address.hex,
            name,
        )

        new_entity = InsteonBinarySensor(device, state_key)

        async_add_entities([new_entity])


class InsteonBinarySensor(InsteonEntity, BinarySensorEntity):
    """A Class for an Insteon device entity."""

    def __init__(self, device, state_key):
        """Initialize the INSTEON binary sensor."""
        super().__init__(device, state_key)
        self._sensor_type = SENSOR_TYPES.get(self._insteon_device_state.name)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        on_val = bool(self._insteon_device_state.value)

        if self._insteon_device_state.name in ["lightSensor", "ioLincSensor"]:
            return not on_val

        return on_val
