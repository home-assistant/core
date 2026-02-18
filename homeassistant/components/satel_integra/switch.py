"""Support for Satel Integra modifiable outputs represented as switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SWITCHABLE_OUTPUT_NUMBER, SUBENTRY_TYPE_SWITCHABLE_OUTPUT
from .coordinator import SatelConfigEntry, SatelIntegraOutputsCoordinator
from .entity import SatelIntegraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra switch devices."""

    runtime_data = config_entry.runtime_data

    switchable_output_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
        config_entry.subentries.values(),
    )

    for subentry in switchable_output_subentries:
        switchable_output_num: int = subentry.data[CONF_SWITCHABLE_OUTPUT_NUMBER]

        async_add_entities(
            [
                SatelIntegraSwitch(
                    runtime_data.coordinator_outputs,
                    config_entry.entry_id,
                    subentry,
                    switchable_output_num,
                    config_entry.options.get(CONF_CODE),
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraSwitch(
    SatelIntegraEntity[SatelIntegraOutputsCoordinator], SwitchEntity
):
    """Representation of an Satel Integra switch."""

    def __init__(
        self,
        coordinator: SatelIntegraOutputsCoordinator,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
        code: str | None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator,
            config_entry_id,
            subentry,
            device_number,
        )

        self._code = code

        self._attr_is_on = self._get_state_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._get_state_from_coordinator()
        self.async_write_ha_state()

    def _get_state_from_coordinator(self) -> bool | None:
        """Method to get switch state from coordinator data."""
        return self.coordinator.data.get(self._device_number)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._controller.set_output(self._code, self._device_number, True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._controller.set_output(self._code, self._device_number, False)
        self._attr_is_on = False
        self.async_write_ha_state()
