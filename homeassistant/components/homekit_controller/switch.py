"""Support for Homekit switches."""
from aiohomekit.model.characteristics import (
    CharacteristicsTypes,
    InUseValues,
    IsConfiguredValues,
)
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

OUTLET_IN_USE = "outlet_in_use"

ATTR_IN_USE = "in_use"
ATTR_IS_CONFIGURED = "is_configured"
ATTR_REMAINING_DURATION = "remaining_duration"


class HomeKitSwitch(HomeKitEntity, SwitchEntity):
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
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        outlet_in_use = self.service.value(CharacteristicsTypes.OUTLET_IN_USE)
        if outlet_in_use is not None:
            return {OUTLET_IN_USE: outlet_in_use}


class HomeKitValve(HomeKitEntity, SwitchEntity):
    """Represents a valve in an irrigation system."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.IN_USE,
            CharacteristicsTypes.IS_CONFIGURED,
            CharacteristicsTypes.REMAINING_DURATION,
        ]

    async def async_turn_on(self, **kwargs):
        """Turn the specified valve on."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: True})

    async def async_turn_off(self, **kwargs):
        """Turn the specified valve off."""
        await self.async_put_characteristics({CharacteristicsTypes.ACTIVE: False})

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ACTIVE)

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        attrs = {}

        in_use = self.service.value(CharacteristicsTypes.IN_USE)
        if in_use is not None:
            attrs[ATTR_IN_USE] = in_use == InUseValues.IN_USE

        is_configured = self.service.value(CharacteristicsTypes.IS_CONFIGURED)
        if is_configured is not None:
            attrs[ATTR_IS_CONFIGURED] = is_configured == IsConfiguredValues.CONFIGURED

        remaining = self.service.value(CharacteristicsTypes.REMAINING_DURATION)
        if remaining is not None:
            attrs[ATTR_REMAINING_DURATION] = remaining

        return attrs


ENTITY_TYPES = {
    ServicesTypes.SWITCH: HomeKitSwitch,
    ServicesTypes.OUTLET: HomeKitSwitch,
    ServicesTypes.VALVE: HomeKitValve,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit switches."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service):
        entity_class = ENTITY_TYPES.get(service.short_type)
        if not entity_class:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
