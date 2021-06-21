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

from .const import ATTR_MANUFACTURER, BRAVIA_CONFIG_FILE, DEFAULT_NAME, DOMAIN

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

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    unique_id = config_entry.unique_id
    device_info = {
        "identifiers": {(DOMAIN, unique_id)},
        "name": DEFAULT_NAME,
        "manufacturer": ATTR_MANUFACTURER,
        "model": config_entry.title,
    }

    async_add_entities(
        [BraviaTVMediaPlayer(coordinator, DEFAULT_NAME, unique_id, device_info)]
    )


class BraviaTVMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Bravia TV Media Player."""

    _attr_device_class = DEVICE_CLASS_TV
    _attr_supported_features = SUPPORT_BRAVIA

    def __init__(self, coordinator, name, unique_id, device_info):
        """Initialize the entity."""

        self._attr_device_info = device_info
        self._attr_is_volume_muted = coordinator.muted
        self._attr_media_content_id = coordinator.channel_name
        self._attr_media_duration = coordinator.duration
        self._attr_name = name
        self._attr_source = coordinator.source
        self._attr_source_list = coordinator.source_list
        self._attr_unique_id = unique_id

        super().__init__(coordinator)

    @property
    def state(self):
        """Return the state of the device."""
        if self.coordinator.is_on:
            return STATE_PLAYING if self.coordinator.playing else STATE_PAUSED
        return STATE_OFF

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self.coordinator.volume is not None:
            return self.coordinator.volume / 100
        return None

    @property
    def media_title(self):
        """Title of current playing media."""
        return_value = None
        if self.coordinator.channel_name is not None:
            return_value = self.coordinator.channel_name
            if self.coordinator.program_name is not None:
                return_value = f"{return_value}: {self.coordinator.program_name}"
        return return_value

    async def async_turn_on(self):
        """Turn the device on."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self):
        """Turn the device off."""
        await self.coordinator.async_turn_off()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self.coordinator.async_set_volume_level(volume)

    async def async_volume_up(self):
        """Send volume up command."""
        await self.coordinator.async_volume_up()

    async def async_volume_down(self):
        """Send volume down command."""
        await self.coordinator.async_volume_down()

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self.coordinator.async_volume_mute(mute)

    async def async_select_source(self, source):
        """Set the input source."""
        await self.coordinator.async_select_source(source)

    async def async_media_play(self):
        """Send play command."""
        await self.coordinator.async_media_play()

    async def async_media_pause(self):
        """Send pause command."""
        await self.coordinator.async_media_pause()

    async def async_media_stop(self):
        """Send media stop command to media player."""
        await self.coordinator.async_media_stop()

    async def async_media_next_track(self):
        """Send next track command."""
        await self.coordinator.async_media_next_track()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self.coordinator.async_media_previous_track()
