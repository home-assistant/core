"""Media player platform for BenQ Projector Infrared integration."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, override

from infrared_protocols.codes.benq.projector import (
    BENQ_PROJECTOR_ADDRESS,
    BenQProjectorCode,
)
from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    POWER_OFF_CONFIRM_DELAY,
    POWER_OFF_CONFIRM_WINDOW,
)
from .entity import BenQProjectorIrEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SOURCE_TO_CODE: dict[str, BenQProjectorCode] = {
    "hdmi_1": BenQProjectorCode.HDMI_1,
    "hdmi_2": BenQProjectorCode.HDMI_2,
    "pc_1": BenQProjectorCode.PC_1,
    "pc_2": BenQProjectorCode.PC_2,
    "component_1": BenQProjectorCode.COMPONENT_1,
    "component_2": BenQProjectorCode.COMPONENT_2,
    "video_1": BenQProjectorCode.VIDEO_1,
    "video_2": BenQProjectorCode.VIDEO_2,
    "s_video_1": BenQProjectorCode.S_VIDEO_1,
    "s_video_2": BenQProjectorCode.S_VIDEO_2,
    "dvi_d": BenQProjectorCode.DVI_D,
    "usb_reader": BenQProjectorCode.USB_READER,
}

CODE_TO_SOURCE: dict[BenQProjectorCode, str] = {
    code: source for source, code in SOURCE_TO_CODE.items()
}


@dataclass
class _BenQProjectorExtraData(ExtraStoredData):
    """Persisted assumed-state data for a BenQ projector.

    Stored separately from the entity state because while the projector is
    OFF, ``MediaPlayerEntity.state_attributes`` strips ``source``, so a
    restart in the OFF state would otherwise lose it. The power state is
    stored too, because the entity state is saved as unavailable when the
    emitter is unavailable at shutdown.
    """

    power_state: MediaPlayerState | None
    source: str | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Serialize for the restore-state store."""
        return {"power_state": self.power_state, "source": self.source}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BenQ Projector Infrared media player from config entry."""
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [BenQProjectorIrMediaPlayerWithReceiver(entry, receiver_entity_id)]
        )
    else:
        async_add_entities([BenQProjectorIrMediaPlayer(entry)])


class BenQProjectorIrMediaPlayer(
    BenQProjectorIrEntity, MediaPlayerEntity, RestoreEntity
):
    """BenQ Projector Infrared media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.PROJECTOR
    _attr_translation_key = "projector"
    _attr_source_list = list(SOURCE_TO_CODE)
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize BenQ Projector Infrared media player."""
        super().__init__(entry, unique_id_suffix="media_player")

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Persist power state and source."""
        return _BenQProjectorExtraData(
            power_state=self._attr_state, source=self._attr_source
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known assumed state and source."""
        await super().async_added_to_hass()

        if (extra := await self.async_get_last_extra_data()) is not None:
            data = extra.as_dict()
            if (power_state := data.get("power_state")) in (
                MediaPlayerState.ON,
                MediaPlayerState.OFF,
            ):
                self._attr_state = MediaPlayerState(power_state)
            if (source := data.get("source")) in SOURCE_TO_CODE:
                self._attr_source = source

    @override
    async def async_turn_on(self) -> None:
        """Send discrete power-on command."""
        await self._send_benq_command(BenQProjectorCode.POWER_ON)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Send discrete power-off command, confirmed by sending it again."""
        await self._send_benq_command(BenQProjectorCode.POWER_OFF)
        await asyncio.sleep(POWER_OFF_CONFIRM_DELAY)
        await self._send_benq_command(BenQProjectorCode.POWER_OFF)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_benq_command(BenQProjectorCode.VOLUME_UP)

    @override
    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_benq_command(BenQProjectorCode.VOLUME_DOWN)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute toggle command.

        BenQ projectors only have a mute toggle, so the mute state is not tracked.
        """
        await self._send_benq_command(BenQProjectorCode.MUTE)

    @override
    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        if (code := SOURCE_TO_CODE.get(source)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": source,
                    "valid_sources": ", ".join(SOURCE_TO_CODE),
                },
            )
        await self._send_benq_command(code)
        self._attr_source = source
        self.async_write_ha_state()


class BenQProjectorIrMediaPlayerWithReceiver(
    BenQProjectorIrMediaPlayer, InfraredReceiverConsumerEntity
):
    """BenQ Projector Infrared media player that follows the physical remote."""

    def __init__(self, entry: ConfigEntry, receiver_entity_id: str) -> None:
        """Initialize BenQ Projector Infrared media player with a receiver."""
        super().__init__(entry)
        self._infrared_receiver_entity_id = receiver_entity_id
        self._power_off_requested_at: datetime | None = None

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update the assumed state from a command sent by the physical remote."""
        nec_command = NECCommand.from_raw_timings(signal.timings)
        if nec_command is None or nec_command.address != BENQ_PROJECTOR_ADDRESS:
            return

        try:
            code = BenQProjectorCode(nec_command.command)
        except ValueError:
            _LOGGER.debug(
                "Ignoring unknown BenQ infrared command: 0x%02X", nec_command.command
            )
            return

        _LOGGER.debug("Received BenQ infrared command: %s", code.name)

        if code is BenQProjectorCode.POWER_ON or (
            code is BenQProjectorCode.POWER and self._attr_state is MediaPlayerState.OFF
        ):
            self._power_off_requested_at = None
            self._attr_state = MediaPlayerState.ON
        elif code is BenQProjectorCode.POWER_OFF or (
            code is BenQProjectorCode.POWER and self._attr_state is MediaPlayerState.ON
        ):
            if not self._async_power_off_confirmed():
                return
            self._attr_state = MediaPlayerState.OFF
        elif code is BenQProjectorCode.POWER:
            return
        elif code is BenQProjectorCode.SOURCE:
            # The source key cycles through the inputs, so the new one is unknown.
            self._attr_source = None
        elif (source := CODE_TO_SOURCE.get(code)) is not None:
            self._attr_source = source
        else:
            return

        self.async_write_ha_state()

    @callback
    def _async_power_off_confirmed(self) -> bool:
        """Return whether a power-off press confirms an earlier one.

        The first press only shows the confirmation prompt on the projector.
        """
        now = dt_util.utcnow()
        requested_at = self._power_off_requested_at
        if requested_at is not None and now - requested_at <= POWER_OFF_CONFIRM_WINDOW:
            self._power_off_requested_at = None
            return True
        self._power_off_requested_at = now
        return False
