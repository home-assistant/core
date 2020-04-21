"""Support for the Tuya scenes."""
from typing import Any

from homeassistant.components.scene import DOMAIN, Scene

from . import DATA_TUYA, TuyaDevice

ENTITY_ID_FORMAT = DOMAIN + ".{}"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tuya scenes."""
    if discovery_info is None:
        return
    tuya = hass.data[DATA_TUYA]
    dev_ids = discovery_info.get("dev_ids")
    devices = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(TuyaScene(device))
    add_entities(devices)


class TuyaScene(TuyaDevice, Scene):
    """Tuya Scene."""

    def __init__(self, tuya):
        """Init Tuya scene."""
        super().__init__(tuya)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.tuya.activate()
