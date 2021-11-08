"""Firmware sensor of the Renson ventilation system."""
import rensonVentilationLib.renson as renson

from homeassistant.components.binary_sensor import BinarySensorEntity


class FirmwareSensor(BinarySensorEntity):
    """Check firmware update and store it in the state of the class."""

    def __init__(self, rensonApi: renson.RensonVentilation, hass):
        """Initialize class."""
        self._state = None
        self.renson = rensonApi
        self.hass = hass

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Latest firmware"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    async def async_update(self):
        """Get firmware and save it in state."""
        self._state = await self.hass.async_add_executor_job(
            self.renson.is_firmware_up_to_date
        )
