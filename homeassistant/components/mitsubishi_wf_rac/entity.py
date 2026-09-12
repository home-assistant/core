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

    Subclasses implement _update_state() and call _apply_state() once at the
    end of their own __init__ for the initial state; this base class
    re-invokes it whenever the coordinator notifies listeners - either from
    its own poll or from Device.async_set_updated_data() right after a
    command completes.
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

        airco.OperationMode keeps reporting it while the unit is off, so this
        is what the displayed mode falls back to - the climate entity's own
        hvac_mode is forced to OFF in that case.
        """
        return list(HVAC_TRANSLATION.keys())[self._device.airco.OperationMode]

    @override
    @property
    def available(self) -> bool:
        """Return whether the airco is currently reachable."""
        # Device tracks its own retry-tolerant availability (see
        # Device._set_availability()): an expected missed poll leaves the
        # coordinator successful on purpose, so last_update_success alone
        # would not hold the entity up. It still has to be honoured, though -
        # an unexpected failure raises UpdateFailed and only shows there.
        return super().available and self._device.available

    def _mark_state_unknown(self) -> None:
        """Drop the attributes that carry this entity's state.

        Overridden per platform. Called when a frame arrives that the entity
        cannot read: the unit answered and still takes commands, so it is not
        unavailable - its state is merely unknown until a frame it can read
        comes along.
        """
        raise NotImplementedError

    def _update_state(self) -> None:
        """Refresh entity state from the coordinator.

        Every concrete subclass overrides this; never invoked through this
        base implementation.
        """
        raise NotImplementedError

    def _apply_state(self) -> None:
        """Read the current frame into this entity, or mark it unknown.

        Every read goes through here, the very first one included. A frame
        can decode cleanly and still carry a value this entity cannot
        translate, and letting that escape a constructor is not the same
        failure as letting it escape a poll: the platform never finishes
        setting up, so the config entry loads with no entity at all and only
        a traceback to say why. The same value arriving one frame later
        merely makes the state unknown.
        """
        try:
            self._update_state()
        except IndexError, KeyError, AttributeError, ValueError:
            # Once, with the traceback: which field was missing is the whole
            # diagnosis, and the condition holds until the unit sends
            # something else - a line per poll would say nothing more.
            if not self._state_unreadable:
                # entity_id is only assigned once the entity is added, so on
                # the first read the unique id is all there is to name it by.
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
