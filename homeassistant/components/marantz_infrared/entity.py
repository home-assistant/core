"""Common entity for Marantz IR integration."""

import logging
from types import ModuleType

from infrared_protocols.codes.marantz import pm6006

from homeassistant.components.infrared import async_send_command
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from . import MarantzIrConfigEntry
from .const import CONF_MODEL, DOMAIN, MarantzModel

_LOGGER = logging.getLogger(__name__)

# Each supported model points at the library module that exposes its codes
# and the ``MODEL_ID`` / ``MODEL_NAME`` constants used for the device
# registry entry.
_MODEL_MODULES: dict[MarantzModel, ModuleType] = {
    MarantzModel.PM6006: pm6006,
}


class MarantzIrEntity(Entity):
    """Marantz IR base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MarantzIrConfigEntry,
        infrared_entity_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize Marantz IR entity."""
        self._infrared_entity_id = infrared_entity_id
        self._runtime_data = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        model_module = _MODEL_MODULES[MarantzModel(entry.data[CONF_MODEL])]
        self._make_command = model_module.make_command
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Marantz {model_module.MODEL_NAME}",
            manufacturer="Marantz",
            model=model_module.MODEL_ID,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared entity state changes."""
        await super().async_added_to_hass()

        @callback
        def _async_ir_state_changed(event: Event[EventStateChangedData]) -> None:
            """Handle infrared entity state changes."""
            new_state = event.data["new_state"]
            ir_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            if ir_available != self.available:
                _LOGGER.info(
                    "Infrared entity %s used by %s is %s",
                    self._infrared_entity_id,
                    self.entity_id,
                    "available" if ir_available else "unavailable",
                )

                self._attr_available = ir_available
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._infrared_entity_id], _async_ir_state_changed
            )
        )

        ir_state = self.hass.states.get(self._infrared_entity_id)
        self._attr_available = (
            ir_state is not None and ir_state.state != STATE_UNAVAILABLE
        )

    async def _send_command(self, code: pm6006.MarantzPM6006Code) -> None:
        """Send an IR command using the Marantz protocol.

        Flips the RC-5 toggle bit before each frame so the receiver
        treats consecutive presses as new presses, not as a held repeat.
        """
        self._runtime_data.toggle ^= 1
        await async_send_command(
            self.hass,
            self._infrared_entity_id,
            self._make_command(code, toggle=self._runtime_data.toggle),
            context=self._context,
        )
