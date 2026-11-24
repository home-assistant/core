"""Common entity for BenQ Projector Infrared integration."""

import math

from infrared_protocols.codes.benq.projector import BenQProjectorCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from . import BenQProjectorIrConfigEntry
from .const import CONF_INFRARED_ENTITY_ID, DEVICE_NAME, DOMAIN


class BenQProjectorIrEntity(InfraredEmitterConsumerEntity):
    """BenQ Projector Infrared base entity."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: BenQProjectorIrConfigEntry, unique_id_suffix: str
    ) -> None:
        """Initialize BenQ Projector Infrared entity."""
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
        self._power_state = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer="BenQ",
        )

    @property
    def _projector_busy(self) -> bool:
        """Return whether the projector is warming up or cooling down."""
        return self._power_state.busy_remaining() is not None

    async def _send_benq_command(self, code: BenQProjectorCode) -> None:
        """Send an IR command to the BenQ projector.

        Raises while the projector warms up or cools down, as it would ignore it.
        """
        if (remaining := self._power_state.busy_remaining()) is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=self._power_state.busy_reason,
                translation_placeholders={
                    "seconds": str(math.ceil(remaining.total_seconds()))
                },
            )
        await self._send_command(code.to_command())
