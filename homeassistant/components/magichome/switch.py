"""Support for MagicHome switches."""
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice

from . import DATA_MAGICHOME, MagicHomeDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up MagicHome Switch device."""
    if discovery_info is None:
        return
    magichome = hass.data[DATA_MAGICHOME]
    dev_ids = discovery_info.get("dev_ids")
    devices = []
    for dev_id in dev_ids:
        device = magichome.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(MagicHomeSwitch(device))
    add_entities(devices)


class MagicHomeSwitch(MagicHomeDevice, SwitchDevice):
    """MagicHome Switch Device."""

    def __init__(self, magichome):
        """Init MagicHome switch device."""
        super().__init__(magichome)
        self.entity_id = ENTITY_ID_FORMAT.format(magichome.object_id())

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.magichome.state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.magichome.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.magichome.turn_off()
