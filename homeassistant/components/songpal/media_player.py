"""Support for Songpal-enabled (Sony) media devices."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging

from songpal import (
    ConnectChange,
    ContentChange,
    Device,
    PowerChange,
    SettingChange,
    SongpalException,
    VolumeChange,
)
from songpal.containers import Setting
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ENDPOINT, DOMAIN, ERROR_REQUEST_RETRY, SET_SOUND_SETTING

_LOGGER = logging.getLogger(__name__)

PARAM_NAME = "name"
PARAM_VALUE = "value"

INITIAL_RETRY_DELAY = 10


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up from legacy configuration file. Obsolete."""
    _LOGGER.error(
        "Configuring Songpal through media_player platform is no longer supported."
        " Convert to songpal platform or UI configuration"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up songpal media player."""
    name = config_entry.data[CONF_NAME]
    endpoint = config_entry.data[CONF_ENDPOINT]

    device = Device(endpoint)
    try:
        async with asyncio.timeout(
            10
        ):  # set timeout to avoid blocking the setup process
            await device.get_supported_methods()
    except (SongpalException, TimeoutError) as ex:
        _LOGGER.warning("[%s(%s)] Unable to connect", name, endpoint)
        _LOGGER.debug("Unable to get methods from songpal: %s", ex)
        raise PlatformNotReady from ex

    songpal_entity = SongpalEntity(name, device)
    async_add_entities([songpal_entity], True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SET_SOUND_SETTING,
        {vol.Required(PARAM_NAME): cv.string, vol.Required(PARAM_VALUE): cv.string},
        "async_set_sound_setting",
    )


class SongpalEntity(MediaPlayerEntity):
    """Class representing a Songpal device."""

    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, name, device):
        """Init."""
        self._name = name
        self._dev = device
        self._sysinfo = None
        self._model = None

        self._state = False
        self._attr_available = False
        self._initialized = False

        self._volume_control = None
        self._volume_min = 0
        self._volume_max = 1
        self._volume = 0
        self._attr_is_volume_muted = False

        self._active_source = None
        self._sources = {}
        self._active_sound_mode = None
        self._sound_modes = {}

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await self.async_activate_websocket()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self._dev.stop_listen_notifications()

    async def _get_sound_modes_info(self):
        """Get available sound modes and the active one."""
        settings = await self._dev.get_sound_settings("soundField")
        if isinstance(settings, Setting):
            settings = [settings]

        sound_modes = {}
        active_sound_mode = None
        for setting in settings:
            cur = setting.currentValue
            for opt in setting.candidate:
                if not opt.isAvailable:
                    continue
                if opt.value == cur:
                    active_sound_mode = opt.value
                sound_modes[opt.value] = opt

        _LOGGER.debug("Got sound modes: %s", sound_modes)
        _LOGGER.debug("Active sound mode: %s", active_sound_mode)

        return active_sound_mode, sound_modes

    async def async_activate_websocket(self):
        """Activate websocket for listening if wanted."""
        _LOGGER.info("Activating websocket connection")

        async def _volume_changed(volume: VolumeChange):
            _LOGGER.debug("Volume changed: %s", volume)
            self._volume = volume.volume
            self._attr_is_volume_muted = volume.mute
            self.async_write_ha_state()

        async def _source_changed(content: ContentChange):
            _LOGGER.debug("Source changed: %s", content)
            if content.is_input:
                self._active_source = self._sources[content.uri]
                _LOGGER.debug("New active source: %s", self._active_source)
                self.async_write_ha_state()
            else:
                _LOGGER.debug("Got non-handled content change: %s", content)

        async def _setting_changed(setting: SettingChange):
            _LOGGER.debug("Setting changed: %s", setting)

            if setting.target == "soundField":
                self._active_sound_mode = setting.currentValue
                _LOGGER.debug("New active sound mode: %s", self._active_sound_mode)
                self.async_write_ha_state()
            else:
                _LOGGER.debug("Got non-handled setting change: %s", setting)

        async def _power_changed(power: PowerChange):
            _LOGGER.debug("Power changed: %s", power)
            self._state = power.status
            self.async_write_ha_state()

        async def _try_reconnect(connect: ConnectChange):
            _LOGGER.warning(
                "[%s(%s)] Got disconnected, trying to reconnect",
                self.name,
                self._dev.endpoint,
            )
            _LOGGER.debug("Disconnected: %s", connect.exception)
            self._attr_available = False
            self.async_write_ha_state()

            # Try to reconnect forever, a successful reconnect will initialize
            # the websocket connection again.
            delay = INITIAL_RETRY_DELAY
            while not self._attr_available:
                _LOGGER.debug("Trying to reconnect in %s seconds", delay)
                await asyncio.sleep(delay)

                try:
                    await self._dev.get_supported_methods()
                except SongpalException as ex:
                    _LOGGER.debug("Failed to reconnect: %s", ex)
                    delay = min(2 * delay, 300)
                else:
                    # We need to inform HA about the state in case we are coming
                    # back from a disconnected state.
                    await self.async_update_ha_state(force_refresh=True)

            self.hass.loop.create_task(self._dev.listen_notifications())
            _LOGGER.warning(
                "[%s(%s)] Connection reestablished", self.name, self._dev.endpoint
            )

        self._dev.on_notification(VolumeChange, _volume_changed)
        self._dev.on_notification(ContentChange, _source_changed)
        self._dev.on_notification(PowerChange, _power_changed)
        self._dev.on_notification(SettingChange, _setting_changed)
        self._dev.on_notification(ConnectChange, _try_reconnect)

        async def handle_stop(event):
            await self._dev.stop_listen_notifications()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)

        self.hass.loop.create_task(self._dev.listen_notifications())

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._sysinfo.macAddr or self._sysinfo.wirelessMacAddr

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        connections = set()
        if self._sysinfo.macAddr:
            connections.add((dr.CONNECTION_NETWORK_MAC, self._sysinfo.macAddr))
        if self._sysinfo.wirelessMacAddr:
            connections.add((dr.CONNECTION_NETWORK_MAC, self._sysinfo.wirelessMacAddr))
        return DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Sony Corporation",
            model=self._model,
            name=self._name,
            sw_version=self._sysinfo.version,
        )

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        _LOGGER.debug("Calling set_sound_setting with %s: %s", name, value)
        await self._dev.set_sound_settings(name, value)

    async def async_update(self) -> None:
        """Fetch updates from the device."""
        try:
            if self._sysinfo is None:
                self._sysinfo = await self._dev.get_system_info()

            if self._model is None:
                interface_info = await self._dev.get_interface_information()
                self._model = interface_info.modelName

            volumes = await self._dev.get_volume_information()
            if not volumes:
                _LOGGER.error("Got no volume controls, bailing out")
                self._attr_available = False
                return

            if len(volumes) > 1:
                _LOGGER.debug("Got %s volume controls, using the first one", volumes)

            volume = volumes[0]
            _LOGGER.debug("Current volume: %s", volume)

            self._volume_max = volume.maxVolume
            self._volume_min = volume.minVolume
            self._volume = volume.volume
            self._volume_control = volume
            self._attr_is_volume_muted = self._volume_control.is_muted

            status = await self._dev.get_power()
            self._state = status.status
            _LOGGER.debug("Got state: %s", status)

            inputs = await self._dev.get_inputs()
            _LOGGER.debug("Got ins: %s", inputs)

            self._sources = OrderedDict()
            for input_ in inputs:
                self._sources[input_.uri] = input_
                if input_.active:
                    self._active_source = input_

            _LOGGER.debug("Active source: %s", self._active_source)

            (
                self._active_sound_mode,
                self._sound_modes,
            ) = await self._get_sound_modes_info()

            self._attr_available = True

        except SongpalException as ex:
            _LOGGER.error("Unable to update: %s", ex)
            self._attr_available = False

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        for out in self._sources.values():
            if out.title == source:
                await out.activate()
                return

        _LOGGER.error("Unable to find output: %s", source)

    @property
    def source_list(self):
        """Return list of available sources."""
        return [src.title for src in self._sources.values()]

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        for mode in self._sound_modes.values():
            if mode.title == sound_mode:
                await self._dev.set_sound_settings("soundField", mode.value)
                return

        _LOGGER.error("Unable to find sound mode: %s", sound_mode)

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return list of available sound modes.

        When active mode is None it means that sound mode is unavailable on the sound bar.
        Can be due to incompatible sound bar or the sound bar is in a mode that does not
        support sound mode changes.
        """
        if not self._active_sound_mode:
            return None
        return [sound_mode.title for sound_mode in self._sound_modes.values()]

    @property
    def state(self) -> MediaPlayerState:
        """Return current state."""
        if self._state:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def source(self):
        """Return currently active source."""
        # Avoid a KeyError when _active_source is not (yet) populated
        return getattr(self._active_source, "title", None)

    @property
    def sound_mode(self) -> str | None:
        """Return currently active sound_mode."""
        active_sound_mode = self._sound_modes.get(self._active_sound_mode)
        return active_sound_mode.title if active_sound_mode else None

    @property
    def volume_level(self):
        """Return volume level."""
        return self._volume / self._volume_max

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        volume = int(volume * self._volume_max)
        _LOGGER.debug("Setting volume to %s", volume)
        return await self._volume_control.set_volume(volume)

    async def async_volume_up(self) -> None:
        """Set volume up."""
        return await self._volume_control.set_volume(self._volume + 1)

    async def async_volume_down(self) -> None:
        """Set volume down."""
        return await self._volume_control.set_volume(self._volume - 1)

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        try:
            return await self._dev.set_power(True)
        except SongpalException as ex:
            if ex.code == ERROR_REQUEST_RETRY:
                _LOGGER.debug(
                    "Swallowing %s, the device might be already in the wanted state", ex
                )
                return
            raise

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        try:
            return await self._dev.set_power(False)
        except SongpalException as ex:
            if ex.code == ERROR_REQUEST_RETRY:
                _LOGGER.debug(
                    "Swallowing %s, the device might be already in the wanted state", ex
                )
                return
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s", mute)
        return await self._volume_control.set_mute(mute)
