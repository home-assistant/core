"""Infrared platform for ESPHome."""

from __future__ import annotations

import logging

from aioesphomeapi import EntityInfo, EntityState, InfraredCapability, InfraredInfo

from homeassistant.components.infrared import InfraredCommand, InfraredEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import EsphomeEntity, async_static_info_updated, convert_api_error_ha_error
from .entry_data import ESPHomeConfigEntry

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPHome infrared entities, filtering out receiver-only devices."""
    entry_data = entry.runtime_data
    entry_data.info[InfraredInfo] = {}
    platform = entity_platform.async_get_current_platform()

    def filtered_static_info_update(infos: list[EntityInfo]) -> None:
        transmitter_infos: list[EntityInfo] = [
            info
            for info in infos
            if isinstance(info, InfraredInfo)
            and info.capabilities & InfraredCapability.TRANSMITTER
        ]
        async_static_info_updated(
            hass,
            entry_data,
            platform,
            async_add_entities,
            InfraredInfo,
            EsphomeInfraredEntity,
            EntityState,
            transmitter_infos,
        )

    entry_data.cleanup_callbacks.append(
        entry_data.async_register_static_info_callback(
            InfraredInfo, filtered_static_info_update
        )
    )
