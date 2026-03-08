"""A sensor for incoming calls using a USB modem that supports caller ID."""

from __future__ import annotations

from phone_modem import PhoneModem

from homeassistant.components.sensor import RestoreSensor
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ModemCallerIdConfigEntry
from .const import CID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModemCallerIdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Modem Caller ID sensor."""
    async_add_entities(
        [
            ModemCalleridSensor(
                entry.runtime_data,
                entry.entry_id,
            )
        ]
    )


class ModemCalleridSensor(RestoreSensor):
    """Implementation of USB modem caller ID sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "incoming_call"

    def __init__(self, api: PhoneModem, server_unique_id: str) -> None:
        """Initialize the sensor."""
        self.api = api
        self._attr_unique_id = server_unique_id
        self._attr_native_value = STATE_IDLE
        self._attr_extra_state_attributes = {
            CID.CID_TIME: 0,
            CID.CID_NUMBER: "",
            CID.CID_NAME: "",
        }
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, server_unique_id)})

    async def async_added_to_hass(self) -> None:
        """Call when the modem sensor is added to Home Assistant."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_extra_state_attributes[CID.CID_NAME] = last_state.attributes.get(
                CID.CID_NAME, ""
            )
            self._attr_extra_state_attributes[CID.CID_NUMBER] = (
                last_state.attributes.get(CID.CID_NUMBER, "")
            )
            self._attr_extra_state_attributes[CID.CID_TIME] = last_state.attributes.get(
                CID.CID_TIME, 0
            )

        self.api.registercallback(self._async_incoming_call)

    @callback
    def _async_incoming_call(self, new_state: str) -> None:
        """Handle new states."""
        self._attr_extra_state_attributes = {}
        if self.api.cid_name:
            self._attr_extra_state_attributes[CID.CID_NAME] = self.api.cid_name
        if self.api.cid_number:
            self._attr_extra_state_attributes[CID.CID_NUMBER] = self.api.cid_number
        if self.api.cid_time:
            self._attr_extra_state_attributes[CID.CID_TIME] = self.api.cid_time
        self._attr_native_value = self.api.state
        self.async_write_ha_state()
