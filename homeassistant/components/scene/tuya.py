"""
Support for the Tuya scene.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.tuya/
"""
from homeassistant.components.scene import Scene, DOMAIN
from homeassistant.components.tuya import DATA_TUYA, TuyaDevice

DEPENDENCIES = ['tuya']

ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya scenes."""
    if discovery_info is None:
        return
    tuya = hass.data[DATA_TUYA]
    dev_ids = discovery_info.get('dev_ids')
    devices = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(TuyaScene(device))
    add_devices(devices)


class TuyaScene(TuyaDevice, Scene):
    """Tuya Scene."""

    def __init__(self, tuya):
        """Init Tuya scene."""
        super().__init__(tuya)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())

    def activate(self):
        """Activate the scene."""
        self.tuya.activate()
