"""Support for the MagicHome scenes."""
from homeassistant.components.scene import DOMAIN, Scene

from . import DATA_MAGICHOME, MagicHomeDevice

ENTITY_ID_FORMAT = DOMAIN + ".{}"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up MagicHome scenes."""
    if discovery_info is None:
        return
    magichome = hass.data[DATA_MAGICHOME]
    dev_ids = discovery_info.get("dev_ids")
    devices = []
    for dev_id in dev_ids:
        device = magichome.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(MagicHomeScene(device))
    add_entities(devices)


class MagicHomeScene(MagicHomeDevice, Scene):
    """MagicHome Scene."""

    def __init__(self, magichome):
        """Init MagicHome scene."""
        super().__init__(magichome)
        self.entity_id = ENTITY_ID_FORMAT.format(magichome.object_id())

    def activate(self):
        """Activate the scene."""
        self.magichome.activate()
