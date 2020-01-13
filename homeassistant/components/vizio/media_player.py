"""Vizio SmartCast Device support."""
from datetime import timedelta
import logging
from typing import Callable, List

from pyvizio import VizioAsync

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
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONF_UNIQUE_ID,
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    DEVICE_ID,
    DOMAIN,
    ICON,
    UPDATE_OPTIONS_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PARALLEL_UPDATES = 0

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
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> bool:
    """Set up a Vizio media player entry."""
    host = config_entry.data[CONF_HOST]
    token = config_entry.data.get(CONF_ACCESS_TOKEN)
    name = config_entry.data[CONF_NAME]
    device_type = config_entry.data[CONF_DEVICE_CLASS]
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)

    # If config entry options not set up, set them up, otherwise assign values managed in options
    if not config_entry.options or CONF_VOLUME_STEP not in config_entry.options:
        volume_step = config_entry.data.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_VOLUME_STEP: volume_step}
        )
    else:
        volume_step = config_entry.options[CONF_VOLUME_STEP]

    device = VizioAsync(
        DEVICE_ID,
        host,
        name,
        token,
        device_type,
        session=async_get_clientsession(hass, False),
    )

    if not await device.can_connect():
        fail_auth_msg = ""
        if token:
            fail_auth_msg = ", auth token is correct"
        _LOGGER.error(
            "Failed to set up Vizio platform, please check if host "
            "is valid and available, device type is correct%s",
            fail_auth_msg,
        )
        raise PlatformNotReady

    entity = VizioDevice(
        hass, config_entry, device, name, volume_step, device_type, unique_id
    )

    async_add_entities([entity], True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to device."""

    def __init__(
        self,
        hass: HomeAssistantType,
        config_entry: ConfigEntry,
        device: VizioAsync,
        name: str,
        volume_step: int,
        device_type: str,
        unique_id: str,
    ) -> None:
        """Initialize Vizio device."""
        self._hass = hass
        self._config_entry = config_entry
        self._async_unsub_listeners = []

        self._name = name
        self._state = None
        self._volume_level = None
        self._volume_step = volume_step
        self._current_input = None
        self._available_inputs = None
        self._device_type = device_type
        self._supported_commands = SUPPORTED_COMMANDS[device_type]
        self._device = device
        self._max_volume = float(self._device.get_max_volume())
        self._unique_id = unique_id
        self._icon = ICON[device_type]
        self._available = True

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    async def async_update(self) -> None:
        """Retrieve latest state of the device."""
        is_on = await self._device.get_power_state()

        if is_on is None:
            self._available = False
            return

        self._available = True

        if not self._unique_id:
            self._unique_id = await self._device.get_esn()

        if not is_on:
            self._state = STATE_OFF
            self._volume_level = None
            self._current_input = None
            self._available_inputs = None
            return

        self._state = STATE_ON

        volume = await self._device.get_current_volume()
        if volume is not None:
            self._volume_level = float(volume) / self._max_volume

        input_ = await self._device.get_current_input()
        if input_ is not None:
            self._current_input = input_.meta_name

        inputs = await self._device.get_inputs()
        if inputs is not None:
            self._available_inputs = [input_.name for input_ in inputs]

    @callback
    @staticmethod
    async def _async_config_entry_updated(
        hass: HomeAssistantType, config_entry: ConfigEntry
    ) -> None:
        """Send update event when when Vizio config entry is updated."""
        async_dispatcher_send(hass, UPDATE_OPTIONS_SIGNAL, config_entry)

    async def _async_maybe_update(self, config_entry: ConfigEntry) -> None:
        """Update options if the update signal comes from this entity."""
        if config_entry.unique_id == self._unique_id:
            self._volume_step = config_entry.options[CONF_VOLUME_STEP]

    async def async_added_to_hass(self):
        """Register callbacks when entity is added."""
        # Register callback for when config entry is updated.
        self._async_unsub_listeners.append(
            self._config_entry.add_update_listener(self._async_config_entry_updated)
        )

        # Register callback for update event
        self._async_unsub_listeners.append(
            async_dispatcher_connect(
                self._hass, UPDATE_OPTIONS_SIGNAL, self._async_maybe_update
            )
        )

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks when entity is removed."""
        if len(self._async_unsub_listeners) > 0:
            for listener in self._async_unsub_listeners:
                listener()

    @property
    def available(self) -> bool:
        """Return the availabiliity of the device."""
        return self._available

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
    def source_list(self) -> List:
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
            "manufacturer": "VIZIO",
        }

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self._device.pow_on()

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self._device.pow_off()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await self._device.mute_on()
        else:
            await self._device.mute_off()

    async def async_media_previous_track(self) -> None:
        """Send previous channel command."""
        await self._device.ch_down()

    async def async_media_next_track(self) -> None:
        """Send next channel command."""
        await self._device.ch_up()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._device.input_switch(source)

    async def async_volume_up(self) -> None:
        """Increasing volume of the device."""
        await self._device.vol_up(self._volume_step)

        if self._volume_level is not None:
            self._volume_level = min(
                1.0, self._volume_level + self._volume_step / self._max_volume
            )

    async def async_volume_down(self) -> None:
        """Decreasing volume of the device."""
        await self._device.vol_down(self._volume_step)

        if self._volume_level is not None:
            self._volume_level = max(
                0.0, self._volume_level - self._volume_step / self._max_volume
            )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        if self._volume_level is not None:
            if volume > self._volume_level:
                num = int(self._max_volume * (volume - self._volume_level))
                await self._device.vol_up(num)
                self._volume_level = volume
            elif volume < self._volume_level:
                num = int(self._max_volume * (self._volume_level - volume))
                await self._device.vol_down(num)
                self._volume_level = volume
