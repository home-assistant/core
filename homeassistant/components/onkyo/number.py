"""Number platform."""

import logging
from typing import TYPE_CHECKING, override

from aioonkyo import status

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ToneControl, ToneCoordinator

if TYPE_CHECKING:
    from . import OnkyoConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnkyoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number platform for config entry."""

    @callback
    def async_add_tone_entities(coordinator: ToneCoordinator) -> None:
        """Add tone control number entities."""
        async_add_entities(
            OnkyoToneNumber(coordinator, control) for control in ToneControl
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_tone",
            async_add_tone_entities,
        )
    )


class OnkyoToneNumber(CoordinatorEntity[ToneCoordinator], NumberEntity):
    """Onkyo Receiver tone control (main zone)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = status.Tone.Param.numeric_range[0]
    _attr_native_max_value = status.Tone.Param.numeric_range[1]
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL

    def __init__(
        self,
        coordinator: ToneCoordinator,
        control: ToneControl,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)

        self._control = control

        name = coordinator.manager.info.model_name
        identifier = coordinator.manager.info.identifier
        self._attr_name = f"{name} {control.capitalize()}"
        self._attr_unique_id = f"{identifier}-tone-{control}"

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available.

        The receiver ignores tone commands while the main zone is off.
        """
        return (
            super().available
            and self.coordinator.manager.connected
            and self.coordinator.power_on
            and self._control in self.coordinator.data
        )

    @property
    @override
    def native_value(self) -> int | None:
        """Return the tone control value."""
        return self.coordinator.data.get(self._control)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the tone control."""
        await self.coordinator.async_send_command(self._control, int(value))
