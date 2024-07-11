"""Provides a binary sensor which is a collection of ffmpeg tools."""

from __future__ import annotations

from typing import Any

import haffmpeg.sensor as ffmpeg_sensor
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
)
from homeassistant.components.ffmpeg import (
    CONF_EXTRA_ARGUMENTS,
    CONF_INITIAL_STATE,
    CONF_INPUT,
    CONF_OUTPUT,
    FFmpegManager,
    get_ffmpeg_manager,
)
from homeassistant.components.ffmpeg_motion.binary_sensor import FFmpegBinarySensor
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_PEAK = "peak"
CONF_DURATION = "duration"
CONF_RESET = "reset"

DEFAULT_NAME = "FFmpeg Noise"
DEFAULT_INIT_STATE = True

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INPUT): cv.string,
        vol.Optional(CONF_INITIAL_STATE, default=DEFAULT_INIT_STATE): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
        vol.Optional(CONF_OUTPUT): cv.string,
        vol.Optional(CONF_PEAK, default=-30): vol.Coerce(int),
        vol.Optional(CONF_DURATION, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_RESET, default=10): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the FFmpeg noise binary sensor."""
    manager = get_ffmpeg_manager(hass)
    entity = FFmpegNoise(hass, manager, config)
    async_add_entities([entity])


class FFmpegNoise(FFmpegBinarySensor[ffmpeg_sensor.SensorNoise]):
    """A binary sensor which use FFmpeg for noise detection."""

    def __init__(
        self, hass: HomeAssistant, manager: FFmpegManager, config: dict[str, Any]
    ) -> None:
        """Initialize FFmpeg noise binary sensor."""

        ffmpeg = ffmpeg_sensor.SensorNoise(manager.binary, self._async_callback)
        super().__init__(ffmpeg, config)

    async def _async_start_ffmpeg(self, entity_ids: list[str] | None) -> None:
        """Start a FFmpeg instance.

        This method is a coroutine.
        """
        if entity_ids is not None and self.entity_id not in entity_ids:
            return

        self.ffmpeg.set_options(
            time_duration=self._config[CONF_DURATION],
            time_reset=self._config[CONF_RESET],
            peak=self._config[CONF_PEAK],
        )

        await self.ffmpeg.open_sensor(
            input_source=self._config[CONF_INPUT],
            output_dest=self._config.get(CONF_OUTPUT),
            extra_cmd=self._config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return BinarySensorDeviceClass.SOUND
