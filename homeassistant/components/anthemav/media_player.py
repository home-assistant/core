"""Support for Anthem Network Receivers and Processors."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ANTHEMAV_UDATE_SIGNAL,
    CONF_MODEL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    MANUFACTURER,
)

DEVICE_CLASS_RECEIVER = "receiver"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up our socket to the AVR."""
    _LOGGER.warning(
        "AnthemAV configuration is deprecated and has been automatically imported. Please remove the integration from your configuration file"
    )
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    name = config_entry.data[CONF_NAME]
    macaddress = config_entry.data[CONF_MAC]
    model = config_entry.data[CONF_MODEL]

    avr = hass.data[DOMAIN][config_entry.entry_id]

    if avr is None:
        raise ConfigEntryNotReady

    device = AnthemAVR(avr, name, macaddress, model)

    _LOGGER.debug("dump_devicedata: %s", device.dump_avrdata)
    _LOGGER.debug("dump_conndata: %s", avr.dump_conndata)

    async_add_devices([device])


class AnthemAVR(MediaPlayerEntity):
    """Entity reading values from Anthem AVR protocol."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, avr, name, macaddress, model):
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._attr_name = name
        self._unique_id = macaddress
        self._model = model
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": name,
            "manufacturer": MANUFACTURER,
            "model": model,
        }

    def _lookup(self, propname, dval=None):
        return getattr(self.avr.protocol, propname, dval)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{ANTHEMAV_UDATE_SIGNAL}_{self._name}",
                self.async_write_ha_state,
            )
        )

    @property
    def state(self):
        """Return state of power on/off."""
        pwrstate = self._lookup("power")

        if pwrstate is True:
            return STATE_ON
        if pwrstate is False:
            return STATE_OFF
        return None

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {"attenuation": self._lookup("attenuation", -90)}

    @property
    def is_volume_muted(self):
        """Return boolean reflecting mute state on device."""
        return self._lookup("mute", False)

    @property
    def volume_level(self):
        """Return volume level from 0 to 1."""
        return self._lookup("volume_as_percentage", 0.0)

    @property
    def media_title(self):
        """Return current input name (closest we have to media title)."""
        return self._lookup("input_name", "No Source")

    @property
    def app_name(self):
        """Return details about current video and audio stream."""
        return (
            f"{self._lookup('video_input_resolution_text', '')} "
            f"{self._lookup('audio_input_name', '')}"
        )

    @property
    def source(self):
        """Return currently selected input."""
        return self._lookup("input_name", "Unknown")

    @property
    def source_list(self):
        """Return all active, configured inputs."""
        return self._lookup("input_list", ["Unknown"])

    @property
    def sound_mode_list(self):
        """Return all available sound mode."""
        if self.state is STATE_OFF:
            return None
        return self._lookup("audio_listening_mode_list", None)

    @property
    def sound_mode(self):
        """Return currently selected sound mode."""
        return self._lookup("audio_listening_mode_text", "Unknown")

    async def async_select_source(self, source):
        """Change AVR to the designated source (by name)."""
        self._update_avr("input_name", source)

    async def async_turn_off(self):
        """Turn AVR power off."""
        self._update_avr("power", False)

    async def async_turn_on(self):
        """Turn AVR power on."""
        self._update_avr("power", True)

    async def async_set_volume_level(self, volume):
        """Set AVR volume (0 to 1)."""
        self._update_avr("volume_as_percentage", volume)

    async def async_volume_up(self):
        """Turn volume up for media player."""
        volume = self.volume_level
        if volume < 1:
            await self.async_set_volume_level(min(1, volume + 0.04))

    async def async_volume_down(self):
        """Turn volume down for media player."""
        volume = self.volume_level
        if volume > 0:
            await self.async_set_volume_level(max(0, volume - 0.04))

    async def async_mute_volume(self, mute):
        """Engage AVR mute."""
        self._update_avr("mute", mute)

    async def async_select_sound_mode(self, sound_mode):
        """Switch the sound mode of the entity."""
        self._update_avr("audio_listening_mode_text", sound_mode)

    def _update_avr(self, propname, value):
        """Update a property in the AVR."""
        _LOGGER.debug("Sending command to AVR: set %s to %s", propname, str(value))
        setattr(self.avr.protocol, propname, value)

    @property
    def dump_avrdata(self):
        """Return state of avr object for debugging forensics."""
        attrs = vars(self)
        items_string = ", ".join(f"{item}: {item}" for item in attrs.items())
        return f"dump_avrdata: {items_string}"
