"""Support for MagicHome socket."""
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice

from . import DATA_MAGICHOME, MagicHomeDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up MagicHome Socket device."""
    if discovery_info is None:
        return
    magichome = hass.data[DATA_MAGICHOME]
    dev_ids = discovery_info.get("dev_ids")
    devices = []
    for dev_id in dev_ids:
        device = magichome.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(MagicHomeSocket(device))
    add_entities(devices)


class MagicHomeSocket(MagicHomeDevice, SwitchDevice):
    """MagicHome Socket Device."""

    def __init__(self, magichome):
        """Init MagicHome socket device."""
        super().__init__(magichome)
        self.entity_id = ENTITY_ID_FORMAT.format(magichome.object_id())

    @property
    def is_on(self):
        """Return true if socket is on."""
        return self.magichome.state()

    def turn_on(self, **kwargs):
        """Turn the socket on."""
        self.magichome.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.magichome.turn_off()
