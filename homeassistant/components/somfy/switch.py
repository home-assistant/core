"""Support for Somfy Camera Shutter."""
from pymfy.api.devices.camera_protect import CameraProtect
from pymfy.api.devices.category import Category

from homeassistant.components.switch import SwitchEntity

from . import SomfyEntity
from .const import API, COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy switch platform."""

    def get_shutters():
        """Retrieve switches."""
        domain_data = hass.data[DOMAIN]
        coordinator = domain_data[COORDINATOR]
        api = domain_data[API]

        return [
            SomfyCameraShutter(coordinator, device_id, api)
            for device_id, device in coordinator.data.items()
            if Category.CAMERA.value in device.categories
        ]

    async_add_entities(await hass.async_add_executor_job(get_shutters), True)


class SomfyCameraShutter(SomfyEntity, SwitchEntity):
    """Representation of a Somfy Camera Shutter device."""

    def __init__(self, coordinator, device_id, api):
        """Initialize the Somfy device."""
        super().__init__(coordinator, device_id, api)
        self._create_device()

    def _create_device(self):
        """Update the device with the latest data."""
        self.shutter = CameraProtect(self.device, self.api)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.shutter.open_shutter()

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        self.shutter.close_shutter()

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.shutter.get_shutter_position() == "opened"
