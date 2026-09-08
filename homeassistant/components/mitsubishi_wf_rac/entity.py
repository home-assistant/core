"""Shared base entity for all WF-RAC platform entities."""

import logging
from typing import Any, override

from homeassistant.components.climate import HVACMode
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_TARGET_OFFSET,
    CONF_TARGET_OFFSET_COOL,
    CONF_TARGET_OFFSET_HEAT,
    HVAC_TRANSLATION,
)
from .coordinator import Device

_LOGGER = logging.getLogger(__name__)


class WfRacEntity(CoordinatorEntity[Device]):
    """Wires an entity to the shared Device coordinator.

    Subclasses keep their existing _update_state() (called once at the end of
    their own __init__ for the initial state, as before); this base class
    re-invokes it whenever the coordinator notifies listeners - either from
    its own poll or from Device.async_set_updated_data() right after a
    command completes.
    """

    def __init__(self, device: Device, context: Any | None = None) -> None:
        """Wire the entity to the shared coordinator."""
        super().__init__(device, context=context)
        self._device = device
        self._attr_device_info = device.device_info
        self._state_unreadable = False

    @property
    def _hvac_mode_from_operation(self) -> HVACMode:
        """The unit's underlying cool/heat mode.

        airco.OperationMode keeps reporting it while the unit is off, which is
        what the offset resolution below needs - the climate entity's own
        hvac_mode is forced to OFF in that case.
        """
        return list(HVAC_TRANSLATION.keys())[self._device.airco.OperationMode]

    def _resolve_target_offset(self, hvac_mode: HVACMode) -> float:
        """Resolve the effective target_offset for a given hvac_mode.

        COOL/DRY take CONF_TARGET_OFFSET_COOL, HEAT takes
        CONF_TARGET_OFFSET_HEAT, and an unset per-mode option falls back to
        the global CONF_TARGET_OFFSET like every other mode. Shared here so
        the write path and the read-back can never resolve a different offset
        for the same mode: they would then correct each other forever.
        """
        options = self._device.options
        base_offset = options.get(CONF_TARGET_OFFSET, 0.0)
        if hvac_mode in (HVACMode.COOL, HVACMode.DRY):
            per_mode = options.get(CONF_TARGET_OFFSET_COOL)
        elif hvac_mode == HVACMode.HEAT:
            per_mode = options.get(CONF_TARGET_OFFSET_HEAT)
        else:
            per_mode = None
        return float(base_offset if per_mode is None else per_mode)

    @override
    @property
    def available(self) -> bool:
        """Return whether the airco is currently reachable and readable."""
        # Device tracks its own retry-tolerant availability (see
        # Device._set_availability()): an expected missed poll leaves the
        # coordinator successful on purpose, so last_update_success alone
        # would not hold the entity up. It still has to be honoured, though -
        # an unexpected failure raises UpdateFailed and only shows there.
        return (
            super().available and self._device.available and not self._state_unreadable
        )

    def _update_state(self) -> None:
        """Refresh entity state from the coordinator.

        Every concrete subclass overrides this; never invoked through this
        base implementation.
        """
        raise NotImplementedError

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        try:
            self._update_state()
        except IndexError, KeyError, AttributeError, ValueError:
            # With the traceback: which field of the device state was missing
            # is the whole diagnosis.
            _LOGGER.warning("Could not update %s", self.entity_id, exc_info=True)
            # Held on the entity, not counted into the device's missed-poll
            # tolerance: the unit answered, this entity just cannot read what
            # it said. Feeding it into that counter would never reach the
            # threshold either, since the successful poll carrying the frame
            # resets it first.
            self._state_unreadable = True
        else:
            self._state_unreadable = False
        self.async_write_ha_state()
