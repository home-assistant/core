"""Representation of an Eltako Series 14 entity."""

import logging

from eltakobus.message import ESP2Message
from eltakobus.util import AddressExpression

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_ID
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import EltakoConfigEntry
from .const import DOMAIN
from .gateway import EltakoGateway

_LOGGER = logging.getLogger(__name__)


class EltakoEntity(Entity):
    """Parent class for all entities associated with the Eltako component."""

    _attr_should_poll = False

    def __init__(
        self, config_entry: EltakoConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the device."""
        self._attr_gateway = config_entry.runtime_data

        self._attr_dev_id = AddressExpression.parse(subentry.data[CONF_ID])
        self._attr_unique_id = (
            f"{subentry.subentry_id}_{self.entity_description.key}"
            if self.entity_description.key
            else subentry.subentry_id
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{subentry.subentry_id}")}
        )

        _LOGGER.debug("Added entity %s (%s)", self.dev_id, type(self).__name__)

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass. Register callback."""
        self.async_on_remove(
            self.gateway.subscribe_address(self.dev_id, self.value_changed)
        )

    @property
    def gateway(self) -> EltakoGateway:
        """Return the supporting gateway of the entity."""
        return self._attr_gateway

    @property
    def dev_id(self) -> AddressExpression:
        """Return the id of the entity."""
        return self._attr_dev_id

    def value_changed(self, msg: ESP2Message) -> None:
        """Update the internal state of the device when a message arrives."""
        raise NotImplementedError("value_changed needs to be implemented")

    async def async_send_message(self, msg: ESP2Message) -> None:
        """Put message on RS485 bus. First the message is put onto HA event bus so that other automations can react on messages."""
        await self.gateway.async_send_message_to_serial_bus(msg)
