"""Support for Satel Integra modifiable outputs represented as switches."""

from __future__ import annotations

from typing import Any

from satel_integra.satel_integra import AsyncSatel

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    SIGNAL_OUTPUTS_UPDATED,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SatelConfigEntry,
)
from .entity import SatelIntegraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra switch devices."""

    controller = config_entry.runtime_data

    switchable_output_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
        config_entry.subentries.values(),
    )

    for subentry in switchable_output_subentries:
        switchable_output_num: int = subentry.data[CONF_SWITCHABLE_OUTPUT_NUMBER]

        async_add_entities(
            [
                SatelIntegraSwitch(
                    controller,
                    config_entry.entry_id,
                    subentry,
                    switchable_output_num,
                    config_entry.options.get(CONF_CODE),
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraSwitch(SatelIntegraEntity, SwitchEntity):
    """Representation of an Satel Integra switch."""

    def __init__(
        self,
        controller: AsyncSatel,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
        code: str | None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            controller,
            config_entry_id,
            subentry,
            device_number,
        )

        self._code = code

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._attr_is_on = self._device_number in self._satel.violated_outputs

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_OUTPUTS_UPDATED, self._devices_updated
            )
        )

    @callback
    def _devices_updated(self, outputs: dict[int, int]) -> None:
        """Update switch state, if needed."""
        if self._device_number in outputs:
            new_state = outputs[self._device_number] == 1
            if new_state != self._attr_is_on:
                self._attr_is_on = new_state
                self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._satel.set_output(self._code, self._device_number, True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._satel.set_output(self._code, self._device_number, False)
        self._attr_is_on = False
        self.async_write_ha_state()
