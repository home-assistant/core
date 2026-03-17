"""Infrared platform for ESPHome."""

from __future__ import annotations

from functools import partial
import logging

from aioesphomeapi import EntityState, InfraredCapability, InfraredInfo

from homeassistant.components.infrared import InfraredCommand, InfraredEntity
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    platform_async_setup_entry,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class EsphomeInfraredEntity(EsphomeEntity[InfraredInfo, EntityState], InfraredEntity):
    """ESPHome infrared entity using native API."""

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Infrared entities should go available as soon as the device comes online
            self.async_write_ha_state()

    @convert_api_error_ha_error
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command."""
        timings = [
            interval
            for timing in command.get_raw_timings()
            for interval in (timing.high_us, -timing.low_us)
        ]
        _LOGGER.debug("Sending command: %s", timings)

        self._client.infrared_rf_transmit_raw_timings(
            self._static_info.key,
            carrier_frequency=command.modulation,
            timings=timings,
            device_id=self._static_info.device_id,
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=InfraredInfo,
    entity_type=EsphomeInfraredEntity,
    state_type=EntityState,
    info_filter=lambda info: bool(info.capabilities & InfraredCapability.TRANSMITTER),
)
