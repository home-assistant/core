"""Infrared platform for ESPHome."""

import functools
import logging
from typing import TYPE_CHECKING

from aioesphomeapi import EntityInfo, EntityState, InfraredCapability, InfraredInfo
from aioesphomeapi.client import InfraredRFReceiveEventModel

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.core import CALLBACK_TYPE, callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    platform_async_setup_entry,
)
from .entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class _EsphomeInfraredEntity(EsphomeEntity[InfraredInfo, EntityState]):
    """Common base for ESPHome infrared entities."""

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Infrared entities should go available as soon as the device comes online
            self.async_write_ha_state()


class EsphomeInfraredEmitterEntity(_EsphomeInfraredEntity, InfraredEmitterEntity):
    """ESPHome infrared emitter entity using native API."""

    @convert_api_error_ha_error
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command."""
        timings = command.get_raw_timings()
        _LOGGER.debug("Sending command: %s", timings)

        self._client.infrared_rf_transmit_raw_timings(
            self._static_info.key,
            carrier_frequency=command.modulation,
            timings=timings,
            device_id=self._static_info.device_id,
        )


class EsphomeInfraredReceiverEntity(_EsphomeInfraredEntity, InfraredReceiverEntity):
    """ESPHome infrared receiver entity using native API."""

    _unsub_receive: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks including IR receive subscription."""
        await super().async_added_to_hass()
        self._async_subscribe_receive()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from the device on entity removal."""
        await super().async_will_remove_from_hass()
        if self._unsub_receive is not None:
            self._unsub_receive()
            self._unsub_receive = None

    @callback
    def _async_subscribe_receive(self) -> None:
        """Subscribe to IR receive events if the device is connected."""
        # Subscribing requires an active API connection; defer to
        # _on_device_update when the device is not (yet) available.
        if self._unsub_receive is not None or not self._entry_data.available:
            return
        self._unsub_receive = self._client.subscribe_infrared_rf_receive(
            self._on_infrared_rf_receive
        )

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            self._async_subscribe_receive()
        elif self._unsub_receive is not None:
            self._unsub_receive = None

    @callback
    def _on_infrared_rf_receive(self, event: InfraredRFReceiveEventModel) -> None:
        """Handle a received IR signal from the device."""
        if (
            event.key != self._static_info.key
            or event.device_id != self._static_info.device_id
        ):
            return
        self._handle_received_signal(InfraredReceivedSignal(timings=event.timings))


def _make_infrared_entity(
    entry_data: RuntimeEntryData,
    info: EntityInfo,
    state_type: type[EntityState],
) -> _EsphomeInfraredEntity:
    """Build the right infrared entity based on the InfraredInfo capabilities."""
    if TYPE_CHECKING:
        assert isinstance(info, InfraredInfo)
    cls = (
        EsphomeInfraredReceiverEntity
        if info.capabilities & InfraredCapability.RECEIVER
        else EsphomeInfraredEmitterEntity
    )
    return cls(entry_data, info, state_type)


async_setup_entry = functools.partial(
    platform_async_setup_entry,
    info_type=InfraredInfo,
    entity_type=_make_infrared_entity,
    state_type=EntityState,
    info_filter=lambda info: bool(
        info.capabilities
        & (InfraredCapability.TRANSMITTER | InfraredCapability.RECEIVER)
    ),
)
