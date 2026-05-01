"""Media player platform for Marantz IR integration."""

from infrared_protocols.codes.marantz.pm6006 import MarantzPM6006Code

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MarantzIrConfigEntry
from .const import CONF_INFRARED_ENTITY_ID, CONF_MODEL, MarantzModel
from .entity import MarantzIrEntity

PARALLEL_UPDATES = 1

# The Optical button on the amp toggles between the two optical inputs and
# the receiver remembers which one was last used, so we cannot deterministically
# pick between Optical 1 and Optical 2 over IR. We expose a single Optical
# entry that just sends the toggle and let the user press again to switch.
SOURCE_TO_CODE: dict[str, MarantzPM6006Code] = {
    "CD": MarantzPM6006Code.SOURCE_CD,
    "Coax": MarantzPM6006Code.SOURCE_COAX,
    "Network": MarantzPM6006Code.SOURCE_NETWORK,
    "Optical": MarantzPM6006Code.SOURCE_OPTICAL,
    "Phono": MarantzPM6006Code.SOURCE_PHONO,
    "Recorder": MarantzPM6006Code.SOURCE_CDR,
    "Tuner": MarantzPM6006Code.SOURCE_TUNER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarantzIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marantz IR media player from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    model = entry.data[CONF_MODEL]
    if model == MarantzModel.PM6006:
        async_add_entities([MarantzIrAmplifierMediaPlayer(entry, infrared_entity_id)])


class MarantzIrAmplifierMediaPlayer(MarantzIrEntity, MediaPlayerEntity):
    """Marantz IR amplifier media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_source_list = list(SOURCE_TO_CODE)
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: MarantzIrConfigEntry, infrared_entity_id: str) -> None:
        """Initialize Marantz IR amplifier media player."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="media_player")
        self._attr_state = MediaPlayerState.ON

    async def async_turn_on(self) -> None:
        """Send the power toggle and assume the amplifier is now on.

        Marantz integrated amplifiers expose only a single POWER toggle
        over IR — there are no discrete on/off codes — so turn-on and
        turn-off send the same frame and rely on assumed_state.
        """
        await self._send_command(MarantzPM6006Code.POWER)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Send the power toggle and assume the amplifier is now off."""
        await self._send_command(MarantzPM6006Code.POWER)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_command(MarantzPM6006Code.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_command(MarantzPM6006Code.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_command(MarantzPM6006Code.MUTE)

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._send_command(SOURCE_TO_CODE[source])
        self._attr_source = source
        self.async_write_ha_state()
