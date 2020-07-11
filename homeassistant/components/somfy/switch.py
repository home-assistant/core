"""Support for Somfy Camera Shutter."""
from pymfy.api.devices.camera_protect import CameraProtect
from pymfy.api.devices.category import Category

from homeassistant.components.switch import SwitchEntity

from . import API, DEVICES, DOMAIN, SomfyEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy switch platform."""

    def get_shutters():
        """Retrieve switches."""
        devices = hass.data[DOMAIN][DEVICES]

        return [
            SomfyCameraShutter(device, hass.data[DOMAIN][API])
            for device in devices
            if Category.CAMERA.value in device.categories
        ]

    async_add_entities(await hass.async_add_executor_job(get_shutters), True)


class SomfyCameraShutter(SomfyEntity, SwitchEntity):
    """Representation of a Somfy Camera Shutter device."""

    def __init__(self, device, api):
        """Initialize the Somfy device."""
        super().__init__(device, api)
        self.shutter = CameraProtect(self.device, self.api)

    async def async_update(self):
        """Update the device with the latest data."""
        await super().async_update()
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
