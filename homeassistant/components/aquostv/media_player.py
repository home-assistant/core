"""Support for interface with an Aquos TV."""

from collections.abc import Callable
import logging
from typing import Any, Concatenate, override

import probatio
import sharp_aquos_rc

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import AquosConfigEntry
from .const import CONF_POWER_ON_ENABLED, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

INTEGRATION_TITLE = "Sharp Aquos TV"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "password"
DEFAULT_TIMEOUT = 0.5
DEFAULT_RETRIES = 2
MAX_VOLUME = 100

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        probatio.Optional(
            probatio.Secret(CONF_PASSWORD), default=DEFAULT_PASSWORD
        ): cv.string,
        probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.string,
        probatio.Optional("retries", default=DEFAULT_RETRIES): cv.string,
        probatio.Optional(CONF_POWER_ON_ENABLED, default=True): cv.boolean,
    }
)

SOURCES = {
    0: "TV / Antenna",
    1: "HDMI_IN_1",
    2: "HDMI_IN_2",
    3: "HDMI_IN_3",
    4: "HDMI_IN_4",
    5: "COMPONENT IN",
    6: "VIDEO_IN_1",
    7: "VIDEO_IN_2",
    8: "PC_IN",
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML platform configuration into a config entry."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sharp Aquos TV media player from a config entry."""
    async_add_entities(
        [
            SharpAquosTVDevice(
                entry,
                entry.runtime_data,
                entry.options.get(CONF_POWER_ON_ENABLED, True),
            )
        ]
    )


def _retry[_SharpAquosTVDeviceT: SharpAquosTVDevice, **_P](
    func: Callable[Concatenate[_SharpAquosTVDeviceT, _P], Any],
) -> Callable[Concatenate[_SharpAquosTVDeviceT, _P], None]:
    """Handle query retries."""

    def wrapper(obj: _SharpAquosTVDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all query functions."""
        update_retries = 5
        while update_retries > 0:
            try:
                func(obj, *args, **kwargs)
                break
            except OSError, TypeError, ValueError:
                update_retries -= 1
                if update_retries == 0:
                    obj.set_state(MediaPlayerState.OFF)

    return wrapper


class SharpAquosTVDevice(MediaPlayerEntity):
    """Representation of a Aquos TV."""

    _attr_source_list = list(SOURCES.values())
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PLAY
    )
    _attr_volume_step = 2 / MAX_VOLUME

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, entry: AquosConfigEntry, remote: sharp_aquos_rc.TV, power_on_enabled: bool
    ) -> None:
        """Initialize the aquos device."""
        self._power_on_enabled = power_on_enabled
        if power_on_enabled:
            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_ON
        self._remote = remote
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Sharp",
        )

    def set_state(self, state: MediaPlayerState) -> None:
        """Set TV state."""
        self._attr_state = state

    @_retry
    def update(self) -> None:
        """Retrieve the latest data."""
        if self._remote.power() == 1:
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF
        if self._power_on_enabled:
            self._remote.power_on_command_settings(2)
        else:
            self._remote.power_on_command_settings(0)
        # Get mute state
        if self._remote.mute() == 2:
            self._attr_is_volume_muted = False
        else:
            self._attr_is_volume_muted = True
        # Get source
        self._attr_source = SOURCES.get(self._remote.input())
        # Get volume
        self._attr_volume_level = self._remote.volume() / MAX_VOLUME

    @_retry
    @override
    def turn_off(self) -> None:
        """Turn off tvplayer."""
        self._remote.power(0)

    @_retry
    @override
    def set_volume_level(self, volume: float) -> None:
        """Set Volume media player."""
        self._remote.volume(round(volume * MAX_VOLUME))

    @_retry
    @override
    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._remote.mute(0)

    @_retry
    @override
    def turn_on(self) -> None:
        """Turn the media player on."""
        self._remote.power(1)

    @_retry
    def media_play_pause(self) -> None:
        """Simulate play pause media player."""
        self._remote.remote_button(40)

    @_retry
    @override
    def media_play(self) -> None:
        """Send play command."""
        self._remote.remote_button(16)

    @_retry
    @override
    def media_pause(self) -> None:
        """Send pause command."""
        self._remote.remote_button(16)

    @_retry
    @override
    def media_next_track(self) -> None:
        """Send next track command."""
        self._remote.remote_button(21)

    @_retry
    @override
    def media_previous_track(self) -> None:
        """Send the previous track command."""
        self._remote.remote_button(19)

    @override
    def select_source(self, source: str) -> None:
        """Set the input source."""
        for key, value in SOURCES.items():
            if source == value:
                self._remote.input(key)
