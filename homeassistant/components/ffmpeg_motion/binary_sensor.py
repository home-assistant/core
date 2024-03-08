"""Provides a binary sensor which is a collection of ffmpeg tools."""

from __future__ import annotations

from typing import Any, TypeVar

from haffmpeg.core import HAFFmpeg
import haffmpeg.sensor as ffmpeg_sensor
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.ffmpeg import (
    CONF_EXTRA_ARGUMENTS,
    CONF_INITIAL_STATE,
    CONF_INPUT,
    FFmpegBase,
    FFmpegManager,
    get_ffmpeg_manager,
)
from homeassistant.const import CONF_NAME, CONF_REPEAT
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_HAFFmpegT = TypeVar("_HAFFmpegT", bound=HAFFmpeg)

CONF_RESET = "reset"
CONF_CHANGES = "changes"
CONF_REPEAT_TIME = "repeat_time"

DEFAULT_NAME = "FFmpeg Motion"
DEFAULT_INIT_STATE = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INPUT): cv.string,
        vol.Optional(CONF_INITIAL_STATE, default=DEFAULT_INIT_STATE): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
        vol.Optional(CONF_RESET, default=10): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_CHANGES, default=10): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=99)
        ),
        vol.Inclusive(CONF_REPEAT, "repeat"): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Inclusive(CONF_REPEAT_TIME, "repeat"): vol.All(
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
    """Set up the FFmpeg binary motion sensor."""
    manager = get_ffmpeg_manager(hass)
    entity = FFmpegMotion(hass, manager, config)
    async_add_entities([entity])


class FFmpegBinarySensor(FFmpegBase[_HAFFmpegT], BinarySensorEntity):
    """A binary sensor which use FFmpeg for noise detection."""

    def __init__(self, ffmpeg: _HAFFmpegT, config: dict[str, Any]) -> None:
        """Init for the binary sensor noise detection."""
        super().__init__(ffmpeg, config[CONF_INITIAL_STATE])

        self._state: bool | None = False
        self._config = config
        self._name: str = config[CONF_NAME]

    @callback
    def _async_callback(self, state: bool | None) -> None:
        """HA-FFmpeg callback for noise detection."""
        self._state = state
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name


class FFmpegMotion(FFmpegBinarySensor[ffmpeg_sensor.SensorMotion]):
    """A binary sensor which use FFmpeg for noise detection."""

    def __init__(
        self, hass: HomeAssistant, manager: FFmpegManager, config: dict[str, Any]
    ) -> None:
        """Initialize FFmpeg motion binary sensor."""
        ffmpeg = ffmpeg_sensor.SensorMotion(manager.binary, self._async_callback)
        super().__init__(ffmpeg, config)

    async def _async_start_ffmpeg(self, entity_ids: list[str] | None) -> None:
        """Start a FFmpeg instance.

        This method is a coroutine.
        """
        if entity_ids is not None and self.entity_id not in entity_ids:
            return

        # init config
        self.ffmpeg.set_options(
            time_reset=self._config[CONF_RESET],
            time_repeat=self._config.get(CONF_REPEAT_TIME, 0),
            repeat=self._config.get(CONF_REPEAT, 0),
            changes=self._config[CONF_CHANGES],
        )

        # run
        await self.ffmpeg.open_sensor(
            input_source=self._config[CONF_INPUT],
            extra_cmd=self._config.get(CONF_EXTRA_ARGUMENTS),
        )

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return BinarySensorDeviceClass.MOTION
