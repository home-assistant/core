"""Radio Frequency platform for ESPHome."""

from __future__ import annotations

from functools import partial
import logging

from aioesphomeapi import (
    EntityState,
    RadioFrequencyCapability,
    RadioFrequencyInfo,
    RadioFrequencyModulation,
)
from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    platform_async_setup_entry,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

MODULATION_TYPE_TO_ESPHOME: dict[ModulationType, RadioFrequencyModulation] = {
    ModulationType.OOK: RadioFrequencyModulation.OOK,
}


class EsphomeRadioFrequencyEntity(
    EsphomeEntity[RadioFrequencyInfo, EntityState], RadioFrequencyTransmitterEntity
):
    """ESPHome radio frequency entity using native API."""

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return supported frequency ranges from device info."""
        return [(self._static_info.frequency_min, self._static_info.frequency_max)]

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            self.async_write_ha_state()

    @convert_api_error_ha_error
    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command."""
        timings = command.get_raw_timings()
        _LOGGER.debug("Sending RF command: %s", timings)

        self._client.radio_frequency_transmit_raw_timings(
            self._static_info.key,
            frequency=command.frequency,
            timings=timings,
            modulation=MODULATION_TYPE_TO_ESPHOME[command.modulation],
            # In ESPHome, repeat_count is total number of times to send the command, while in rf_protocols
            # it's the number of additional times to send it, so we need to add 1 here.
            repeat_count=command.repeat_count + 1,
            device_id=self._static_info.device_id,
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=RadioFrequencyInfo,
    entity_type=EsphomeRadioFrequencyEntity,
    state_type=EntityState,
    info_filter=lambda info: bool(
        info.capabilities & RadioFrequencyCapability.TRANSMITTER
    ),
)
