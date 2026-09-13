"""Support for AquaLogic switches."""

from typing import Any, override

from aqualogic.core import States

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquaLogicConfigEntry, AquaLogicProcessor
from .const import UPDATE_TOPIC

_SWITCH_MAP: dict[str, tuple[str, States]] = {
    "lights": ("Lights", States.LIGHTS),
    "filter": ("Filter", States.FILTER),
    "filter_low_speed": ("Filter Low Speed", States.FILTER_LOW_SPEED),
    "aux_1": ("Aux 1", States.AUX_1),
    "aux_2": ("Aux 2", States.AUX_2),
    "aux_3": ("Aux 3", States.AUX_3),
    "aux_4": ("Aux 4", States.AUX_4),
    "aux_5": ("Aux 5", States.AUX_5),
    "aux_6": ("Aux 6", States.AUX_6),
    "aux_7": ("Aux 7", States.AUX_7),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquaLogicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch entities."""
    processor = entry.runtime_data

    async_add_entities(
        AquaLogicSwitch(processor, switch_type) for switch_type in _SWITCH_MAP
    )


class AquaLogicSwitch(SwitchEntity):
    """Switch implementation for the AquaLogic component."""

    _attr_should_poll = False

    def __init__(self, processor: AquaLogicProcessor, switch_type: str) -> None:
        """Initialize switch."""
        name, state = _SWITCH_MAP[switch_type]
        self._processor = processor
        self._state_name = state
        self._attr_name = f"AquaLogic {name}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true if device is on."""
        if (panel := self._processor.panel) is None:
            return False
        return panel.get_state(self._state_name)  # type: ignore[no-any-return]

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if (panel := self._processor.panel) is None:
            return
        panel.set_state(self._state_name, True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if (panel := self._processor.panel) is None:
            return
        panel.set_state(self._state_name, False)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_TOPIC, self.async_write_ha_state)
        )
