"""Support for Homekit switches."""
from aiohomekit.model.characteristics import (
    Characteristic,
    CharacteristicsTypes,
    InUseValues,
    IsConfiguredValues,
)
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback

from . import KNOWN_DEVICES, CharacteristicEntity, HomeKitEntity

OUTLET_IN_USE = "outlet_in_use"

ATTR_IN_USE = "in_use"
ATTR_IS_CONFIGURED = "is_configured"
ATTR_REMAINING_DURATION = "remaining_duration"


SIMPLE_SWITCH: dict[str, SwitchEntityDescription] = {
    CharacteristicsTypes.Vendor.HAA_SETUP: SwitchEntityDescription(
        key=CharacteristicsTypes.Vendor.HAA_SETUP,
        name="Setup",
    ),
    CharacteristicsTypes.Vendor.HAA_UPDATE: SwitchEntityDescription(
        key=CharacteristicsTypes.Vendor.HAA_UPDATE,
        name="Update",
    ),
}


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


class SimpleSwitch(CharacteristicEntity, HomeKitSwitch):
    """
    A simple switch for a single characteristic.

    This may be an additional secondary entity that is part of another service. An
    example is a device that has an OTA update switch.

    These *have* to have a different unique_id to the normal sensors as there could
    be multiple entities per HomeKit service (this was not previously the case).
    """

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        conn,
        info,
        char,
        description: SwitchEntityDescription,
    ):
        """Initialize switch."""
        super().__init__(conn, info, char)
        self.entity_description = description

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        name = super().name
        if name:
            return f"{name} - {self.entity_description.name}"
        return f"{self.entity_description.name}"

    @property
    def native_value(self):
        """Return the current switch value."""
        return self._char.value

    async def async_turn_on(self, **kwargs):
        """Turn the specified switch on."""
        key = self.entity_description.key
        vendor = CharacteristicsTypes.Vendor
        if key in {vendor.HAA_SETUP, vendor.HAA_UPDATE}:
            return await self.async_put_characteristics({key: "#HAA@trcmd"})
        return await super().async_turn_on(**kwargs)


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
        if not (entity_class := ENTITY_TYPES.get(service.short_type)):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)

    @callback
    def async_add_characteristic(char: Characteristic):
        if not (description := SIMPLE_SWITCH.get(char.type)):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        async_add_entities([SimpleSwitch(conn, info, char, description)], True)

        return True

    conn.add_char_factory(async_add_characteristic)
