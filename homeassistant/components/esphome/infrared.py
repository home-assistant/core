"""Infrared platform for ESPHome."""

from __future__ import annotations

import logging

from aioesphomeapi import EntityInfo, EntityState, InfraredCapability, InfraredInfo
from aioesphomeapi.client import InfraredRFReceiveEventModel
from infrared_protocols import Timing as InfraredTiming

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    platform_async_setup_entry,
)
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class EsphomeInfraredEmitterEntity(
    EsphomeEntity[InfraredInfo, EntityState], InfraredEmitterEntity
):
    """ESPHome infrared emitter entity using native API."""

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


class EsphomeInfraredReceiverEntity(
    EsphomeEntity[InfraredInfo, EntityState], InfraredReceiverEntity
):
    """ESPHome infrared receiver entity using native API."""

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        entity_info: InfraredInfo,
        state_type: type[EntityState],
    ) -> None:
        """Initialize the receiver entity."""
        InfraredReceiverEntity.__init__(self)
        EsphomeEntity.__init__(self, entry_data, entity_info, state_type)

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Update static info and ensure unique_id has receiver suffix."""
        super()._on_static_info_update(static_info)
        self._attr_unique_id = f"{self._attr_unique_id}-rx"

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks including IR receive subscription."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._client.subscribe_infrared_rf_receive(
                self._on_infrared_rf_receive,
            )
        )

    @callback
    def _on_infrared_rf_receive(self, event: InfraredRFReceiveEventModel) -> None:
        """Handle a received IR signal from the device."""
        if (
            event.key != self._static_info.key
            or event.device_id != self._static_info.device_id
        ):
            return

        timings = [
            InfraredTiming(high_us=event.timings[i], low_us=abs(event.timings[i + 1]))
            for i in range(0, len(event.timings) - 1, 2)
        ]
        signal = InfraredReceivedSignal(timings=timings)
        self._handle_received_signal(signal)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPHome infrared entities."""
    entry_data = entry.runtime_data

    # Set up emitter entities via the standard platform setup
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=InfraredInfo,
        entity_type=EsphomeInfraredEmitterEntity,
        state_type=EntityState,
        info_filter=lambda info: bool(
            info.capabilities & InfraredCapability.TRANSMITTER
        ),
    )

    # Set up receiver entities via a second registration
    # We need a separate info tracking dict for receivers since
    # platform_async_setup_entry overwrites entry_data.info[InfraredInfo]
    receiver_entities: dict[tuple[int, int], EsphomeInfraredReceiverEntity] = {}

    @callback
    def _on_receiver_info_update(infos: list[EntityInfo]) -> None:
        """Handle receiver static info updates."""
        receiver_infos = [
            info
            for info in infos
            if isinstance(info, InfraredInfo)
            and info.capabilities & InfraredCapability.RECEIVER
        ]

        new_entities: list[EsphomeInfraredReceiverEntity] = []
        new_keys: set[tuple[int, int]] = set()

        for info in receiver_infos:
            info_key = (info.device_id, info.key)
            new_keys.add(info_key)
            if info_key not in receiver_entities:
                entity = EsphomeInfraredReceiverEntity(entry_data, info, EntityState)
                receiver_entities[info_key] = entity
                new_entities.append(entity)

        # Remove entities that are no longer present
        for info_key in list(receiver_entities):
            if info_key not in new_keys:
                del receiver_entities[info_key]

        if new_entities:
            async_add_entities(new_entities)

    entry_data.cleanup_callbacks.append(
        entry_data.async_register_static_info_callback(
            InfraredInfo,
            _on_receiver_info_update,
        )
    )
