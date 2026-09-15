"""Shared base entity for all WF-RAC platform entities."""

import logging
from typing import override

from homeassistant.components.climate import HVACMode
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import HVAC_TRANSLATION
from .coordinator import Device

_LOGGER = logging.getLogger(__name__)


class WfRacEntity(CoordinatorEntity[Device]):
    """Wires an entity to the shared Device coordinator.

    Subclasses implement _update_state() and call _apply_state() at the end of
    their own __init__.
    """

    def __init__(self, device: Device) -> None:
        """Wire the entity to the shared coordinator."""
        super().__init__(device)
        self._device = device
        self._attr_device_info = device.device_info
        self._state_unreadable = False

    @property
    def _hvac_mode_from_operation(self) -> HVACMode:
        """The unit's underlying cool/heat mode.

        Reported while the unit is off too, which is why the climate entity
        forces its own hvac_mode to OFF instead.
        """
        return list(HVAC_TRANSLATION.keys())[self._device.airco.OperationMode]

    def _mark_state_unknown(self) -> None:
        """Drop the attributes that carry this entity's state.

        For a frame the entity cannot read: the unit answered and still takes
        commands, so its state is unknown rather than unavailable.
        """
        raise NotImplementedError

    def _update_state(self) -> None:
        """Refresh entity state from the coordinator, overridden per platform."""
        raise NotImplementedError

    def _apply_state(self) -> None:
        """Read the current frame into this entity, or mark it unknown.

        Every read goes through here, the constructor's included: a value it
        cannot translate must not escape there and abort the platform setup.
        """
        try:
            self._update_state()
        except IndexError, KeyError, AttributeError, ValueError:
            # Once, with the traceback: the condition holds until the unit
            # sends something else, and a line per poll says nothing more.
            if not self._state_unreadable:
                # entity_id exists only once the entity is added.
                _LOGGER.warning(
                    "Could not update %s",
                    self.entity_id or self._attr_unique_id,
                    exc_info=True,
                )
            self._state_unreadable = True
            self._mark_state_unknown()
        else:
            self._state_unreadable = False

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        self._apply_state()
        self.async_write_ha_state()
