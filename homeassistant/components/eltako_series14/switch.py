"""Support for Eltako Series 14 switches."""

import logging
from typing import Any

from eltakobus.eep import A5_38_08, F6_02_01, M5_38_08, CentralCommandSwitching
from eltakobus.message import ESP2Message
from eltakobus.util import AddressExpression

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EltakoConfigEntry
from .const import CONF_SENDER_ID
from .device import MODELS, SwitchEntities
from .entity import EltakoEntity

_LOGGER = logging.getLogger(__name__)


class EltakoStandardSwitch(EltakoEntity, SwitchEntity):
    """Representation of an Eltako switch device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self, config_entry: EltakoConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the Eltako switch device."""
        super().__init__(config_entry, subentry)
        self._sender_id = AddressExpression.parse(subentry.data[CONF_SENDER_ID])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        address, _ = self._sender_id

        switching = CentralCommandSwitching(0, 1, 0, 0, 1)
        msg = A5_38_08(command=0x01, switching=switching).encode_message(address)
        await self.async_send_message(msg)

        if self.gateway.fast_status_change:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        address, _ = self._sender_id

        switching = CentralCommandSwitching(0, 1, 0, 0, 0)
        msg = A5_38_08(command=0x01, switching=switching).encode_message(address)
        await self.async_send_message(msg)

        if self.gateway.fast_status_change:
            self._attr_is_on = False
            self.schedule_update_ha_state()

    def value_changed(self, msg: ESP2Message) -> None:
        """Update the internal state of the switch."""
        decoded = M5_38_08.decode_message(msg)

        self._attr_is_on = decoded.state
        self.schedule_update_ha_state()


class EltakoDumbSwitch(EltakoStandardSwitch):
    """Representation of a dumb Eltako switch.

    This is for devices, which do not support the controller telegrams (e.g. FMS14).
    Therefore pressing a button is simulated.
    """

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        address, _ = self._sender_id

        msg = F6_02_01(3, 1, 0, 0).encode_message(address)  # push button
        await self.async_send_message(msg)
        msg = F6_02_01(3, 0, 0, 0).encode_message(address)  # release button
        await self.async_send_message(msg)

        if self.gateway.fast_status_change:
            self._attr_is_on = True
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        address, _ = self._sender_id

        msg = F6_02_01(2, 1, 0, 0).encode_message(address)  # push button
        await self.async_send_message(msg)
        msg = F6_02_01(2, 0, 0, 0).encode_message(address)  # release button
        await self.async_send_message(msg)

        if self.gateway.fast_status_change:
            self._attr_is_on = False
            self.schedule_update_ha_state()


ENTITY_CLASS_MAP: dict[SwitchEntities, type[EltakoEntity]] = {
    SwitchEntities.STANDARD: EltakoStandardSwitch,
    SwitchEntities.DUMB: EltakoDumbSwitch,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EltakoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Eltako switch platform."""

    # Add devices' entities
    for subentry_id, subentry in config_entry.subentries.items():
        device_model = MODELS[subentry.data[CONF_MODEL]]
        subentry_entities = [
            ENTITY_CLASS_MAP[entity_type](config_entry, subentry)
            for entity_type in device_model.switches
            if ENTITY_CLASS_MAP.get(entity_type)
        ]
        async_add_entities(subentry_entities, config_subentry_id=subentry_id)
