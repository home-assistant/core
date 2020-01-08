"""Vizio SmartCast Device support."""

from datetime import timedelta
import logging

from pyvizio import Vizio

from homeassistant import util
from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_VOLUME_STEP, DEFAULT_NAME, DEVICE_ID, DOMAIN, ICON

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

COMMON_SUPPORTED_COMMANDS = (
    SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

SUPPORTED_COMMANDS = {
    "soundbar": COMMON_SUPPORTED_COMMANDS,
    "tv": (COMMON_SUPPORTED_COMMANDS | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK),
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up a Vizio media player entry."""

    host = entry.data[CONF_HOST]
    token = entry.data.get(CONF_ACCESS_TOKEN)
    name = entry.data[CONF_NAME]
    volume_step = entry.data[CONF_VOLUME_STEP]
    device_type = entry.data[CONF_DEVICE_CLASS]
    device = VizioDevice(hass, host, token, name, volume_step, device_type)

    if not await hass.async_add_executor_job(device.validate_setup):
        fail_auth_msg = ""
        if token:
            fail_auth_msg = " and auth token is correct"
        _LOGGER.error(
            "Failed to set up Vizio platform, please check if host "
            "is valid and available, device type is correct, %s",
            fail_auth_msg,
        )

        return False

    return async_add_entities([device], True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to device."""

    def __init__(
        self,
        hass: HomeAssistantType,
        host: str,
        token: str,
        name: str,
        volume_step: int,
        device_type: str,
        model: str = None,
    ) -> None:
        """Initialize Vizio device."""

        self._hass = hass
        self._name = name
        self._state = None
        self._volume_level = None
        self._volume_step = volume_step
        self._current_input = None
        self._available_inputs = None
        self._device_type = device_type
        self._supported_commands = SUPPORTED_COMMANDS[device_type]
        self._device = Vizio(DEVICE_ID, host, DEFAULT_NAME, token, device_type)
        self._max_volume = float(self._device.get_max_volume())
        self._unique_id = None
        self._model = model
        self._icon = ICON[device_type]

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    async def async_update(self) -> None:
        """Retrieve latest state of the device."""

        if not self._unique_id:
            self._unique_id = await self._hass.async_add_executor_job(
                self._device.get_esn
            )

        is_on = await self._hass.async_add_executor_job(self._device.get_power_state)

        if is_on:
            self._state = STATE_ON

            volume = await self._hass.async_add_executor_job(
                self._device.get_current_volume
            )
            if volume is not None:
                self._volume_level = float(volume) / self._max_volume

            input_ = await self._hass.async_add_executor_job(
                self._device.get_current_input
            )
            if input_ is not None:
                self._current_input = input_.meta_name

            inputs = await self._hass.async_add_executor_job(self._device.get_inputs)
            if inputs is not None:
                self._available_inputs = [input_.name for input_ in inputs]

        else:
            if is_on is None:
                self._state = None
            else:
                self._state = STATE_OFF

            self._volume_level = None
            self._current_input = None
            self._available_inputs = None

    @property
    def state(self) -> str:
        """Return the state of the device."""

        return self._state

    @property
    def name(self) -> str:
        """Return the name of the device."""

        return self._name

    @property
    def icon(self) -> str:
        """Return the icon of the device."""

        return self._icon

    @property
    def volume_level(self) -> float:
        """Return the volume level of the device."""

        return self._volume_level

    @property
    def source(self) -> str:
        """Return current input of the device."""

        return self._current_input

    @property
    def source_list(self) -> list:
        """Return list of available inputs of the device."""

        return self._available_inputs

    @property
    def supported_features(self) -> int:
        """Flag device features that are supported."""

        return self._supported_commands

    @property
    def unique_id(self) -> str:
        """Return the unique id of the device."""

        return self._unique_id

    @property
    def device_info(self):
        """Return device registry information."""

        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self.name,
            "manufacturer": "Vizio",
            "model": self._model,
        }

    async def async_turn_on(self) -> None:
        """Turn the device on."""

        await self._hass.async_add_executor_job(self._device.pow_on)

    async def async_turn_off(self) -> None:
        """Turn the device off."""

        await self._hass.async_add_executor_job(self._device.pow_off)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""

        if mute:
            await self._hass.async_add_executor_job(self._device.mute_on)
        else:
            await self._hass.async_add_executor_job(self._device.mute_off)

    async def async_media_previous_track(self) -> None:
        """Send previous channel command."""

        await self._hass.async_add_executor_job(self._device.ch_down)

    async def async_media_next_track(self) -> None:
        """Send next channel command."""

        await self._hass.async_add_executor_job(self._device.ch_up)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""

        await self._hass.async_add_executor_job(self._device.input_switch, source)

    async def async_volume_up(self) -> None:
        """Increasing volume of the device."""

        await self._hass.async_add_executor_job(self._device.vol_up, self._volume_step)
        if self._volume_level is not None:
            self._volume_level = min(
                1.0, self._volume_level + self._volume_step / self._max_volume
            )

    async def async_volume_down(self) -> None:
        """Decreasing volume of the device."""

        await self._hass.async_add_executor_job(
            self._device.vol_down, self._volume_step
        )
        if self._volume_level is not None:
            self._volume_level = max(
                0.0, self._volume_level - self._volume_step / self._max_volume
            )

    def validate_setup(self) -> bool:
        """Validate if host is available and auth token is correct."""

        return self._device.can_connect()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""

        if self._volume_level is not None:
            if volume > self._volume_level:
                num = int(self._max_volume * (volume - self._volume_level))
                self._volume_level = volume
                await self._hass.async_add_executor_job(self._device.vol_up, num)
            elif volume < self._volume_level:
                num = int(self._max_volume * (self._volume_level - volume))
                self._volume_level = volume
                await self._hass.async_add_executor_job(self._device.vol_down, num)
