"""Vizio SmartCast Device support."""
from datetime import timedelta
import logging
from typing import Callable, List

from pyvizio import VizioAsync

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_TIMEOUT,
    DEFAULT_VOLUME_STEP,
    DEVICE_ID,
    DOMAIN,
    ICON,
    SUPPORTED_COMMANDS,
    VIZIO_DEVICE_CLASSES,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up a Vizio media player entry."""
    host = config_entry.data[CONF_HOST]
    token = config_entry.data.get(CONF_ACCESS_TOKEN)
    name = config_entry.data[CONF_NAME]
    device_class = config_entry.data[CONF_DEVICE_CLASS]

    # If config entry options not set up, set them up, otherwise assign values managed in options
    volume_step = config_entry.options.get(
        CONF_VOLUME_STEP, config_entry.data.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP),
    )

    params = {}
    if not config_entry.options:
        params["options"] = {CONF_VOLUME_STEP: volume_step}

    if not config_entry.data.get(CONF_VOLUME_STEP):
        new_data = config_entry.data.copy()
        new_data.update({CONF_VOLUME_STEP: volume_step})
        params["data"] = new_data

    if params:
        hass.config_entries.async_update_entry(config_entry, **params)

    device = VizioAsync(
        DEVICE_ID,
        host,
        name,
        auth_token=token,
        device_type=VIZIO_DEVICE_CLASSES[device_class],
        session=async_get_clientsession(hass, False),
        timeout=DEFAULT_TIMEOUT,
    )

    if not await device.can_connect():
        _LOGGER.warning("Failed to connect to %s", host)
        raise PlatformNotReady

    entity = VizioDevice(config_entry, device, name, volume_step, device_class)

    async_add_entities([entity], update_before_add=True)


class VizioDevice(MediaPlayerDevice):
    """Media Player implementation which performs REST requests to device."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        device: VizioAsync,
        name: str,
        volume_step: int,
        device_class: str,
    ) -> None:
        """Initialize Vizio device."""
        self._config_entry = config_entry
        self._async_unsub_listeners = []

        self._name = name
        self._state = None
        self._volume_level = None
        self._volume_step = volume_step
        self._current_input = None
        self._available_inputs = None
        self._device_class = device_class
        self._supported_commands = SUPPORTED_COMMANDS[device_class]
        self._device = device
        self._max_volume = float(self._device.get_max_volume())
        self._icon = ICON[device_class]
        self._available = True
        self._model = None
        self._sw_version = None

    async def async_update(self) -> None:
        """Retrieve latest state of the device."""
        if not self._model:
            self._model = await self._device.get_model()

        if not self._sw_version:
            self._sw_version = await self._device.get_version()

        is_on = await self._device.get_power_state(log_api_exception=False)

        if is_on is None:
            if self._available:
                _LOGGER.warning(
                    "Lost connection to %s", self._config_entry.data[CONF_HOST]
                )
                self._available = False
            return

        if not self._available:
            _LOGGER.info(
                "Restored connection to %s", self._config_entry.data[CONF_HOST]
            )
            self._available = True

        if not is_on:
            self._state = STATE_OFF
            self._volume_level = None
            self._current_input = None
            self._available_inputs = None
            return

        self._state = STATE_ON

        volume = await self._device.get_current_volume(log_api_exception=False)
        if volume is not None:
            self._volume_level = float(volume) / self._max_volume

        input_ = await self._device.get_current_input(log_api_exception=False)
        if input_ is not None:
            self._current_input = input_

        inputs = await self._device.get_inputs_list(log_api_exception=False)
        if inputs is not None:
            self._available_inputs = [input_.name for input_ in inputs]

    @staticmethod
    async def _async_send_update_options_signal(
        hass: HomeAssistantType, config_entry: ConfigEntry
    ) -> None:
        """Send update event when Vizio config entry is updated."""
        # Move this method to component level if another entity ever gets added for a single config entry.
        # See here: https://github.com/home-assistant/home-assistant/pull/30653#discussion_r366426121
        async_dispatcher_send(hass, config_entry.entry_id, config_entry)

    async def _async_update_options(self, config_entry: ConfigEntry) -> None:
        """Update options if the update signal comes from this entity."""
        self._volume_step = config_entry.options[CONF_VOLUME_STEP]

    async def async_added_to_hass(self):
        """Register callbacks when entity is added."""
        # Register callback for when config entry is updated.
        self._async_unsub_listeners.append(
            self._config_entry.add_update_listener(
                self._async_send_update_options_signal
            )
        )

        # Register callback for update event
        self._async_unsub_listeners.append(
            async_dispatcher_connect(
                self.hass, self._config_entry.entry_id, self._async_update_options
            )
        )

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks when entity is removed."""
        for listener in self._async_unsub_listeners:
            listener()

        self._async_unsub_listeners.clear()

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
        return self._config_entry.unique_id

    @property
    def device_info(self):
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
            "name": self.name,
            "manufacturer": "VIZIO",
            "model": self._model,
            "sw_version": self._sw_version,
        }

    @property
    def device_class(self):
        """Return device class for entity."""
        return self._device_class

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
        await self._device.set_input(source)

    async def async_volume_up(self) -> None:
        """Increase volume of the device."""
        await self._device.vol_up(num=self._volume_step)

        if self._volume_level is not None:
            self._volume_level = min(
                1.0, self._volume_level + self._volume_step / self._max_volume
            )

    async def async_volume_down(self) -> None:
        """Decrease volume of the device."""
        await self._device.vol_down(num=self._volume_step)

        if self._volume_level is not None:
            self._volume_level = max(
                0.0, self._volume_level - self._volume_step / self._max_volume
            )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        if self._volume_level is not None:
            if volume > self._volume_level:
                num = int(self._max_volume * (volume - self._volume_level))
                await self._device.vol_up(num=num)
                self._volume_level = volume

            elif volume < self._volume_level:
                num = int(self._max_volume * (self._volume_level - volume))
                await self._device.vol_down(num=num)
                self._volume_level = volume
