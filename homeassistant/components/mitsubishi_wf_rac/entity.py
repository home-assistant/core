"""Shared base entity for all WF-RAC platform entities."""

import logging
from typing import Any, override

from homeassistant.components.climate.const import HVACMode
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

        COOL/DRY fall back to CONF_TARGET_OFFSET_COOL, HEAT to
        CONF_TARGET_OFFSET_HEAT, everything else always uses the global
        CONF_TARGET_OFFSET - and so does COOL/HEAT when its per-mode option
        is unset (None), which is what keeps single-target_offset installs
        unchanged. Lives on the base entity so the climate write path, the
        climate read-back path and the target temperature sensor can never
        resolve a different offset for the same mode (see beta2: that
        divergence is what caused the target_temperature re-send loop).
        """
        options = self._device.options
        base_offset = options.get(CONF_TARGET_OFFSET, 0.0)
        if hvac_mode in (HVACMode.COOL, HVACMode.DRY):
            override = options.get(CONF_TARGET_OFFSET_COOL)
        elif hvac_mode == HVACMode.HEAT:
            override = options.get(CONF_TARGET_OFFSET_HEAT)
        else:
            override = None
        return float(base_offset if override is None else override)

    @override
    @property
    def available(self) -> bool:
        """Return whether the airco is currently reachable."""
        # Device tracks its own retry-tolerant availability (see
        # Device._set_availability()), and entities follow that rather than the
        # coordinator's last_update_success: an expected missed poll leaves the
        # coordinator successful on purpose, so this is the only thing that
        # decides whether entities go unavailable.
        return self._device.available

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
            _LOGGER.warning("Could not update %s", self.entity_id)
            self._device.set_available(False)
        self.async_write_ha_state()
