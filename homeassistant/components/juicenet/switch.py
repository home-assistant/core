"""Support for monitoring juicenet/juicepoint/juicebox based EVSE switches."""
import logging

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN, JuicenetDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Juicenet switch."""
    api = hass.data[DOMAIN]["api"]

    devs = []
    for device in api.get_devices():
        devs.append(JuicenetChargeNowSwitch(device, hass))

    add_entities(devs)


class JuicenetChargeNowSwitch(JuicenetDevice, SwitchEntity):
    """Implementation of a Juicenet switch."""

    def __init__(self, device, hass):
        """Initialise the switch."""
        super().__init__(device, "charge_now", hass)

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self.device.name()} Charge Now"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.getOverrideTime() != 0

    def turn_on(self, **kwargs):
        """Charge now."""
        self.device.setOverride(True)

    def turn_off(self, **kwargs):
        """Don't charge now."""
        self.device.setOverride(False)
