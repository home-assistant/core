"""Support for Homekit switches."""
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes

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

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [CharacteristicsTypes.ON, CharacteristicsTypes.OUTLET_IN_USE]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ON)

    async def async_turn_on(self, **kwargs):
        """Turn the specified switch on."""
        await self.async_put_characteristics({CharacteristicsTypes.ON: True})

    async def async_turn_off(self, **kwargs):
        """Turn the specified switch off."""
        await self.async_put_characteristics({CharacteristicsTypes.ON: False})

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        outlet_in_use = self.service.value(CharacteristicsTypes.OUTLET_IN_USE)
        if outlet_in_use is not None:
            return {OUTLET_IN_USE: outlet_in_use}
