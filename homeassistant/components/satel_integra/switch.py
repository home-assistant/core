"""Support for Satel Integra modifiable outputs represented as switches."""

from __future__ import annotations

import logging
from typing import Any

from satel_integra.satel_integra import AsyncSatel

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_CODE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    SIGNAL_OUTPUTS_UPDATED,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SatelConfigEntry,
)

_LOGGER = logging.getLogger(__name__)


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
        switchable_output_name: str = subentry.data[CONF_NAME]

        async_add_entities(
            [
                SatelIntegraSwitch(
                    controller,
                    switchable_output_num,
                    switchable_output_name,
                    config_entry.options.get(CONF_CODE),
                    config_entry.entry_id,
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraSwitch(SwitchEntity):
    """Representation of an Satel switch."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        controller: AsyncSatel,
        device_number: int,
        device_name: str,
        code: str | None,
        config_entry_id: str,
    ) -> None:
        """Initialize the switch."""
        self._device_number = device_number
        self._attr_unique_id = f"{config_entry_id}_switch_{device_number}"
        self._state = False
        self._code = code
        self._satel = controller

        self._attr_name = device_name

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._state = self._read_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_OUTPUTS_UPDATED, self._devices_updated
            )
        )

    @callback
    def _devices_updated(self, outputs: dict[int, int]) -> None:
        """Update switch state, if needed."""
        _LOGGER.debug("Update switch name: %s zones: %s", self._attr_name, outputs)
        if self._device_number in outputs:
            new_state = self._read_state()
            _LOGGER.debug("New state: %s", new_state)
            if new_state != self._state:
                self._state = new_state
                self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        _LOGGER.debug("Switch: %s status: %s, turning on", self._attr_name, self._state)
        await self._satel.set_output(self._code, self._device_number, True)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        _LOGGER.debug(
            "Switch name: %s status: %s, turning off", self._attr_name, self._state
        )
        await self._satel.set_output(self._code, self._device_number, False)
        self._state = False
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._state

    def _read_state(self) -> bool:
        """Read state of the device."""
        return self._device_number in self._satel.violated_outputs
