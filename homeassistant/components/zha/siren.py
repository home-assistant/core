"""Support for ZHA sirens."""
from __future__ import annotations

from collections.abc import Callable
import functools
from typing import TYPE_CHECKING, Any, cast

from zigpy.zcl.clusters.security import IasWd as WD

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .core import discovery
from .core.channels.security import IasWd
from .core.const import (
    CHANNEL_IAS_WD,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    WARNING_DEVICE_MODE_BURGLAR,
    WARNING_DEVICE_MODE_EMERGENCY,
    WARNING_DEVICE_MODE_EMERGENCY_PANIC,
    WARNING_DEVICE_MODE_FIRE,
    WARNING_DEVICE_MODE_FIRE_PANIC,
    WARNING_DEVICE_MODE_POLICE_PANIC,
    WARNING_DEVICE_MODE_STOP,
    WARNING_DEVICE_SOUND_HIGH,
    WARNING_DEVICE_STROBE_HIGH,
    WARNING_DEVICE_STROBE_NO,
    Strobe,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.channels.base import ZigbeeChannel
    from .core.device import ZHADevice

MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.SIREN)
DEFAULT_DURATION = 5  # seconds


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation siren from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.SIREN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


@MULTI_MATCH(channel_names=CHANNEL_IAS_WD)
class ZHASiren(ZhaEntity, SirenEntity):
    """Representation of a ZHA siren."""

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs,
    ) -> None:
        """Init this siren."""
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON
            | SirenEntityFeature.TURN_OFF
            | SirenEntityFeature.DURATION
            | SirenEntityFeature.VOLUME_SET
            | SirenEntityFeature.TONES
        )
        self._attr_available_tones: list[int | str] | dict[int, str] | None = {
            WARNING_DEVICE_MODE_BURGLAR: "Burglar",
            WARNING_DEVICE_MODE_FIRE: "Fire",
            WARNING_DEVICE_MODE_EMERGENCY: "Emergency",
            WARNING_DEVICE_MODE_POLICE_PANIC: "Police Panic",
            WARNING_DEVICE_MODE_FIRE_PANIC: "Fire Panic",
            WARNING_DEVICE_MODE_EMERGENCY_PANIC: "Emergency Panic",
        }
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel: IasWd = cast(IasWd, channels[0])
        self._attr_is_on: bool = False
        self._off_listener: Callable[[], None] | None = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on siren."""
        if self._off_listener:
            self._off_listener()
            self._off_listener = None
        tone_cache = self._channel.data_cache.get(WD.Warning.WarningMode.__name__)
        siren_tone = (
            tone_cache.value
            if tone_cache is not None
            else WARNING_DEVICE_MODE_EMERGENCY
        )
        siren_duration = DEFAULT_DURATION
        level_cache = self._channel.data_cache.get(WD.Warning.SirenLevel.__name__)
        siren_level = (
            level_cache.value if level_cache is not None else WARNING_DEVICE_SOUND_HIGH
        )
        strobe_cache = self._channel.data_cache.get(Strobe.__name__)
        should_strobe = (
            strobe_cache.value if strobe_cache is not None else Strobe.No_Strobe
        )
        strobe_level_cache = self._channel.data_cache.get(WD.StrobeLevel.__name__)
        strobe_level = (
            strobe_level_cache.value
            if strobe_level_cache is not None
            else WARNING_DEVICE_STROBE_HIGH
        )
        if (duration := kwargs.get(ATTR_DURATION)) is not None:
            siren_duration = duration
        if (tone := kwargs.get(ATTR_TONE)) is not None:
            siren_tone = tone
        if (level := kwargs.get(ATTR_VOLUME_LEVEL)) is not None:
            siren_level = int(level)
        await self._channel.issue_start_warning(
            mode=siren_tone,
            warning_duration=siren_duration,
            siren_level=siren_level,
            strobe=should_strobe,
            strobe_duty_cycle=50 if should_strobe else 0,
            strobe_intensity=strobe_level,
        )
        self._attr_is_on = True
        self._off_listener = async_call_later(
            self._zha_device.hass, siren_duration, self.async_set_off
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off siren."""
        await self._channel.issue_start_warning(
            mode=WARNING_DEVICE_MODE_STOP, strobe=WARNING_DEVICE_STROBE_NO
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def async_set_off(self, _) -> None:
        """Set is_on to False and write HA state."""
        self._attr_is_on = False
        if self._off_listener:
            self._off_listener()
            self._off_listener = None
        self.async_write_ha_state()
