"""Radio Frequency platform for ESPHome."""

from functools import partial
import logging
from typing import TYPE_CHECKING, override

from aioesphomeapi import (
    EntityInfo,
    EntityState,
    RadioFrequencyCapability,
    RadioFrequencyInfo,
    RadioFrequencyModulation,
)
from aioesphomeapi.client import InfraredRFReceiveEventModel
from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.components.radio_frequency import (
    RadioFrequencyReceivedSignal,
    RadioFrequencyReceiverEntity,
    RadioFrequencyTransmitterEntity,
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

MODULATION_TYPE_TO_ESPHOME: dict[ModulationType, RadioFrequencyModulation] = {
    ModulationType.OOK: RadioFrequencyModulation.OOK,
}


class _EsphomeRadioFrequencyEntity(EsphomeEntity[RadioFrequencyInfo, EntityState]):
    """Common base for ESPHome radio frequency entities."""

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return supported frequency ranges from device info."""
        return [(self._static_info.frequency_min, self._static_info.frequency_max)]

    @callback
    @override
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            self.async_write_ha_state()


class EsphomeRadioFrequencyTransmitterEntity(
    _EsphomeRadioFrequencyEntity, RadioFrequencyTransmitterEntity
):
    """ESPHome radio frequency transmitter entity using native API."""

    @convert_api_error_ha_error
    @override
    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command."""
        timings = command.get_raw_timings()
        _LOGGER.debug("Sending RF command: %s", timings)

        self._client.radio_frequency_transmit_raw_timings(
            self._static_info.key,
            frequency=command.frequency,
            timings=timings,
            modulation=MODULATION_TYPE_TO_ESPHOME[command.modulation],
            # In ESPHome, repeat_count is total number of
            # times to send the command, while in rf_protocols
            # it's the number of additional times to send it,
            # so we need to add 1 here.
            repeat_count=command.repeat_count + 1,
            device_id=self._static_info.device_id,
        )


class EsphomeRadioFrequencyReceiverEntity(
    _EsphomeRadioFrequencyEntity, RadioFrequencyReceiverEntity
):
    """ESPHome radio frequency receiver entity using native API."""

    _unsub_receive: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks including RF receive subscription."""
        await super().async_added_to_hass()
        self._async_subscribe_receive()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from the device on entity removal."""
        await super().async_will_remove_from_hass()
        if self._unsub_receive is not None:
            self._unsub_receive()
            self._unsub_receive = None

    @callback
    def _async_subscribe_receive(self) -> None:
        """Subscribe to RF receive events if the device is connected."""
        # Subscribing requires an active API connection
        if self._unsub_receive is not None or not self._entry_data.available:
            return
        self._unsub_receive = self._client.subscribe_infrared_rf_receive(
            self._on_infrared_rf_receive
        )

    @callback
    @override
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            self._async_subscribe_receive()
        elif self._unsub_receive is not None:
            self._unsub_receive = None

    @callback
    def _on_infrared_rf_receive(self, event: InfraredRFReceiveEventModel) -> None:
        """Handle a received RF signal from the device."""
        if (
            event.key != self._static_info.key
            or event.device_id != self._static_info.device_id
        ):
            return
        self._handle_received_signal(
            RadioFrequencyReceivedSignal(timings=event.timings)
        )


def _make_radio_frequency_entity(
    entry_data: RuntimeEntryData,
    info: EntityInfo,
    state_type: type[EntityState],
) -> _EsphomeRadioFrequencyEntity:
    """Build the right radio frequency entity based on the capabilities."""
    if TYPE_CHECKING:
        assert isinstance(info, RadioFrequencyInfo)
    cls = (
        EsphomeRadioFrequencyReceiverEntity
        if info.capabilities & RadioFrequencyCapability.RECEIVER
        else EsphomeRadioFrequencyTransmitterEntity
    )
    return cls(entry_data, info, state_type)


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=RadioFrequencyInfo,
    entity_type=_make_radio_frequency_entity,
    state_type=EntityState,
    info_filter=lambda info: bool(
        info.capabilities
        & (RadioFrequencyCapability.TRANSMITTER | RadioFrequencyCapability.RECEIVER)
    ),
)
