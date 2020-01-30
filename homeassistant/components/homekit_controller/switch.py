"""Support for Homekit switches."""
import logging

from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

OUTLET_IN_USE = "outlet_in_use"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lock."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        if service["stype"] not in ("switch", "outlet"):
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([HomeKitSwitch(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitSwitch(HomeKitEntity, SwitchDevice):
    """Representation of a Homekit switch."""

    def __init__(self, *args):
        """Initialise the switch."""
        super().__init__(*args)
        self._on = None
        self._outlet_in_use = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [CharacteristicsTypes.ON, CharacteristicsTypes.OUTLET_IN_USE]

    def _update_on(self, value):
        self._on = value

    def _update_outlet_in_use(self, value):
        self._outlet_in_use = value

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._on

    async def async_turn_on(self, **kwargs):
        """Turn the specified switch on."""
        self._on = True
        characteristics = [{"aid": self._aid, "iid": self._chars["on"], "value": True}]
        await self._accessory.put_characteristics(characteristics)

    async def async_turn_off(self, **kwargs):
        """Turn the specified switch off."""
        characteristics = [{"aid": self._aid, "iid": self._chars["on"], "value": False}]
        await self._accessory.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._outlet_in_use is not None:
            return {OUTLET_IN_USE: self._outlet_in_use}
