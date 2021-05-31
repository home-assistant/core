"""Support for interface with a Bravia TV."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    DEVICE_CLASS_TV,
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.json import load_json

from .const import (
    ATTR_MANUFACTURER,
    BRAVIA_CLIENT,
    BRAVIA_CONFIG_FILE,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_BRAVIA = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_STOP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Bravia TV platform."""
    host = config[CONF_HOST]

    bravia_config_file_path = hass.config.path(BRAVIA_CONFIG_FILE)
    bravia_config = await hass.async_add_executor_job(
        load_json, bravia_config_file_path
    )
    if not bravia_config:
        _LOGGER.error(
            "Configuration import failed, there is no bravia.conf file in the configuration folder"
        )
        return

    while bravia_config:
        # Import a configured TV
        host_ip, host_config = bravia_config.popitem()
        if host_ip == host:
            pin = host_config[CONF_PIN]

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={CONF_HOST: host, CONF_PIN: pin},
                )
            )
            return


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Bravia TV Media Player from a config_entry."""

    client = hass.data[DOMAIN][config_entry.entry_id][BRAVIA_CLIENT]
    unique_id = config_entry.unique_id
    device_info = {
        "identifiers": {(DOMAIN, unique_id)},
        "name": DEFAULT_NAME,
        "manufacturer": ATTR_MANUFACTURER,
        "model": config_entry.title,
    }

    async_add_entities(
        [BraviaTVMediaPlayer(client, DEFAULT_NAME, unique_id, device_info)]
    )


class BraviaTVMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Bravia TV Media Player."""

    def __init__(self, client, name, unique_id, device_info):
        """Initialize the entity."""

        self._name = name
        self._client = client
        self._unique_id = unique_id
        self._device_info = device_info

        super().__init__(client)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Set the device class to TV."""
        return DEVICE_CLASS_TV

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def state(self):
        """Return the state of the device."""
        if self._client.is_on:
            return STATE_PLAYING if self._client.playing else STATE_PAUSED
        return STATE_OFF

    @property
    def source(self):
        """Return the current input source."""
        return self._client.source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._client.source_list

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._client.volume is not None:
            return self._client.volume / 100
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._client.muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_BRAVIA

    @property
    def media_title(self):
        """Title of current playing media."""
        return_value = None
        if self._client.channel_name is not None:
            return_value = self._client.channel_name
            if self._client.program_name is not None:
                return_value = f"{return_value}: {self._client.program_name}"
        return return_value

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._client.channel_name

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._client.duration

    async def async_turn_on(self):
        """Turn the device on."""
        await self._client.async_turn_on()

    async def async_turn_off(self):
        """Turn the device off."""
        await self._client.async_turn_off()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._client.async_set_volume_level(volume)

    async def async_volume_up(self):
        """Send volume up command."""
        await self._client.async_volume_up()

    async def async_volume_down(self):
        """Send volume down command."""
        await self._client.async_volume_down()

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self._client.async_volume_mute(mute)

    async def async_select_source(self, source):
        """Set the input source."""
        await self._client.async_select_source(source)

    async def async_media_play_pause(self):
        """Send play/pause command."""
        await self._client.async_media_play_pause()

    async def async_media_play(self):
        """Send play command."""
        await self._client.async_media_play()

    async def async_media_pause(self):
        """Send pause command."""
        await self._client.async_media_pause()

    async def async_media_stop(self):
        """Send media stop command to media player."""
        await self._client.async_media_stop()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._client.async_media_next_track()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._client.async_media_previous_track()
