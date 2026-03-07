"""Vizio SmartCast Device support."""

from __future__ import annotations

from pyvizio.api.apps import AppConfig, find_app_name
from pyvizio.const import APP_HOME, INPUT_APPS, NO_APP_RUNNING, UNKNOWN_APP

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DATA_APPS
from .const import (
    CONF_ADDITIONAL_CONFIGS,
    CONF_APPS,
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    SUPPORTED_COMMANDS,
    VIZIO_AUDIO_SETTINGS,
    VIZIO_MUTE,
    VIZIO_MUTE_ON,
    VIZIO_SOUND_MODE,
    VIZIO_VOLUME,
)
from .coordinator import (
    VizioAppsDataUpdateCoordinator,
    VizioConfigEntry,
    VizioDeviceCoordinator,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Vizio media player entry."""
    device_class = config_entry.data[CONF_DEVICE_CLASS]

    # If config entry options not set up, set them up,
    # otherwise assign values managed in options
    volume_step = config_entry.options.get(
        CONF_VOLUME_STEP, config_entry.data.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
    )

    params = {}
    if not config_entry.options:
        params["options"] = {CONF_VOLUME_STEP: volume_step}

        include_or_exclude_key = next(
            (
                key
                for key in config_entry.data.get(CONF_APPS, {})
                if key in (CONF_INCLUDE, CONF_EXCLUDE)
            ),
            None,
        )
        if include_or_exclude_key:
            params["options"][CONF_APPS] = {
                include_or_exclude_key: config_entry.data[CONF_APPS][
                    include_or_exclude_key
                ].copy()
            }

    if not config_entry.data.get(CONF_VOLUME_STEP):
        new_data = config_entry.data.copy()
        new_data.update({CONF_VOLUME_STEP: volume_step})
        params["data"] = new_data

    if params:
        hass.config_entries.async_update_entry(
            config_entry,
            **params,  # type: ignore[arg-type]
        )

    entity = VizioDevice(
        config_entry,
        device_class,
        config_entry.runtime_data.device_coordinator,
        hass.data.get(DATA_APPS) if device_class == MediaPlayerDeviceClass.TV else None,
    )

    async_add_entities([entity])


class VizioDevice(CoordinatorEntity[VizioDeviceCoordinator], MediaPlayerEntity):
    """Media Player implementation which performs REST requests to device."""

    _attr_has_entity_name = True
    _attr_name = None
    _current_input: str | None = None
    _current_app_config: AppConfig | None = None

    def __init__(
        self,
        config_entry: VizioConfigEntry,
        device_class: MediaPlayerDeviceClass,
        coordinator: VizioDeviceCoordinator,
        apps_coordinator: VizioAppsDataUpdateCoordinator | None,
    ) -> None:
        """Initialize Vizio device."""
        super().__init__(coordinator)

        self._config_entry = config_entry
        self._apps_coordinator = apps_coordinator
        self._attr_sound_mode_list = []
        self._available_inputs: list[str] = []
        self._available_apps: list[str] = []

        self._volume_step = config_entry.options[CONF_VOLUME_STEP]
        self._all_apps = apps_coordinator.data if apps_coordinator else None
        self._conf_apps = config_entry.options.get(CONF_APPS, {})
        self._additional_app_configs = config_entry.data.get(CONF_APPS, {}).get(
            CONF_ADDITIONAL_CONFIGS, []
        )
        self._device = coordinator.device
        self._max_volume = float(coordinator.device.get_max_volume())

        # Entity class attributes that will change with each update (we only include
        # the ones that are initialized differently from the defaults)
        self._attr_supported_features = SUPPORTED_COMMANDS[device_class]

        # Entity class attributes that will not change
        unique_id = config_entry.unique_id
        assert unique_id
        self._attr_unique_id = unique_id
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    def _apps_list(self, apps: list[str]) -> list[str]:
        """Return process apps list based on configured filters."""
        if self._conf_apps.get(CONF_INCLUDE):
            return [app for app in apps if app in self._conf_apps[CONF_INCLUDE]]

        if self._conf_apps.get(CONF_EXCLUDE):
            return [app for app in apps if app not in self._conf_apps[CONF_EXCLUDE]]

        return apps

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data

        # Handle device off
        if not data.is_on:
            self._attr_state = MediaPlayerState.OFF
            self._attr_volume_level = None
            self._attr_is_volume_muted = None
            self._attr_sound_mode = None
            self._attr_app_name = None
            self._current_input = None
            self._current_app_config = None
            super()._handle_coordinator_update()
            return

        # Device is on - apply coordinator data
        self._attr_state = MediaPlayerState.ON

        # Audio settings
        if data.audio_settings:
            self._attr_volume_level = (
                float(data.audio_settings[VIZIO_VOLUME]) / self._max_volume
            )
            if VIZIO_MUTE in data.audio_settings:
                self._attr_is_volume_muted = (
                    data.audio_settings[VIZIO_MUTE].lower() == VIZIO_MUTE_ON
                )
            else:
                self._attr_is_volume_muted = None
            if VIZIO_SOUND_MODE in data.audio_settings:
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.SELECT_SOUND_MODE
                )
                self._attr_sound_mode = data.audio_settings[VIZIO_SOUND_MODE]
                if not self._attr_sound_mode_list:
                    self._attr_sound_mode_list = data.sound_mode_list or []
            else:
                self._attr_supported_features &= (
                    ~MediaPlayerEntityFeature.SELECT_SOUND_MODE
                )

        # Input state
        if data.current_input:
            self._current_input = data.current_input
        if data.input_list:
            self._available_inputs = [i.name for i in data.input_list]

        # App state (TV only) - check if device supports apps
        if (
            self._attr_device_class == MediaPlayerDeviceClass.TV
            and self._available_inputs
            and any(app in self._available_inputs for app in INPUT_APPS)
        ):
            all_apps = self._all_apps or ()
            self._available_apps = self._apps_list([app["name"] for app in all_apps])
            self._current_app_config = data.current_app_config
            self._attr_app_name = find_app_name(
                self._current_app_config,
                [APP_HOME, *all_apps, *self._additional_app_configs],
            )
            if self._attr_app_name == NO_APP_RUNNING:
                self._attr_app_name = None

        super()._handle_coordinator_update()

    def _get_additional_app_names(self) -> list[str]:
        """Return list of additional apps that were included in configuration.yaml."""
        return [
            additional_app["name"] for additional_app in self._additional_app_configs
        ]

    @staticmethod
    async def _async_send_update_options_signal(
        hass: HomeAssistant, config_entry: VizioConfigEntry
    ) -> None:
        """Send update event when Vizio config entry is updated."""
        # Move this method to component level if another entity ever gets added for a
        # single config entry.
        # See here: https://github.com/home-assistant/core/pull/30653#discussion_r366426121
        async_dispatcher_send(hass, config_entry.entry_id, config_entry)

    async def _async_update_options(self, config_entry: VizioConfigEntry) -> None:
        """Update options if the update signal comes from this entity."""
        self._volume_step = config_entry.options[CONF_VOLUME_STEP]
        # Update so that CONF_ADDITIONAL_CONFIGS gets retained for imports
        self._conf_apps.update(config_entry.options.get(CONF_APPS, {}))

    async def async_update_setting(
        self, setting_type: str, setting_name: str, new_value: int | str
    ) -> None:
        """Update a setting when update_setting service is called."""
        await self._device.set_setting(
            setting_type,
            setting_name,
            new_value,
            log_api_exception=False,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()

        # Process initial coordinator data
        self._handle_coordinator_update()

        # Register callback for when config entry is updated.
        self.async_on_remove(
            self._config_entry.add_update_listener(
                self._async_send_update_options_signal
            )
        )

        # Register callback for update event
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._config_entry.entry_id, self._async_update_options
            )
        )

        if not (apps_coordinator := self._apps_coordinator):
            return

        # Register callback for app list updates if device is a TV
        @callback
        def apps_list_update() -> None:
            """Update list of all apps."""
            self._all_apps = apps_coordinator.data
            self.async_write_ha_state()

        self.async_on_remove(apps_coordinator.async_add_listener(apps_list_update))

    @property
    def source(self) -> str | None:
        """Return current input of the device."""
        if self._attr_app_name is not None and self._current_input in INPUT_APPS:
            return self._attr_app_name

        return self._current_input

    @property
    def source_list(self) -> list[str]:
        """Return list of available inputs of the device."""
        # If Smartcast app is in input list, and the app list has been retrieved,
        # show the combination with, otherwise just return inputs
        if self._available_apps:
            return [
                *(
                    _input
                    for _input in self._available_inputs
                    if _input not in INPUT_APPS
                ),
                *self._available_apps,
                *(
                    app
                    for app in self._get_additional_app_names()
                    if app not in self._available_apps
                ),
            ]

        return self._available_inputs

    @property
    def app_id(self):
        """Return the ID of the current app if it is unknown by pyvizio."""
        if self._current_app_config and self.source == UNKNOWN_APP:
            return {
                "APP_ID": self._current_app_config.APP_ID,
                "NAME_SPACE": self._current_app_config.NAME_SPACE,
                "MESSAGE": self._current_app_config.MESSAGE,
            }

        return None

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        if sound_mode in (self._attr_sound_mode_list or ()):
            await self._device.set_setting(
                VIZIO_AUDIO_SETTINGS,
                VIZIO_SOUND_MODE,
                sound_mode,
                log_api_exception=False,
            )

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self._device.pow_on(log_api_exception=False)

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self._device.pow_off(log_api_exception=False)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await self._device.mute_on(log_api_exception=False)
            self._attr_is_volume_muted = True
        else:
            await self._device.mute_off(log_api_exception=False)
            self._attr_is_volume_muted = False

    async def async_media_previous_track(self) -> None:
        """Send previous channel command."""
        await self._device.ch_down(log_api_exception=False)

    async def async_media_next_track(self) -> None:
        """Send next channel command."""
        await self._device.ch_up(log_api_exception=False)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source in self._available_inputs:
            await self._device.set_input(source, log_api_exception=False)
        elif source in self._get_additional_app_names():
            await self._device.launch_app_config(
                **next(
                    app["config"]
                    for app in self._additional_app_configs
                    if app["name"] == source
                ),
                log_api_exception=False,
            )
        elif source in self._available_apps:
            await self._device.launch_app(
                source, self._all_apps, log_api_exception=False
            )

    async def async_volume_up(self) -> None:
        """Increase volume of the device."""
        await self._device.vol_up(num=self._volume_step, log_api_exception=False)

        if self._attr_volume_level is not None:
            self._attr_volume_level = min(
                1.0, self._attr_volume_level + self._volume_step / self._max_volume
            )

    async def async_volume_down(self) -> None:
        """Decrease volume of the device."""
        await self._device.vol_down(num=self._volume_step, log_api_exception=False)

        if self._attr_volume_level is not None:
            self._attr_volume_level = max(
                0.0, self._attr_volume_level - self._volume_step / self._max_volume
            )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        if self._attr_volume_level is not None:
            if volume > self._attr_volume_level:
                num = int(self._max_volume * (volume - self._attr_volume_level))
                await self._device.vol_up(num=num, log_api_exception=False)
                self._attr_volume_level = volume

            elif volume < self._attr_volume_level:
                num = int(self._max_volume * (self._attr_volume_level - volume))
                await self._device.vol_down(num=num, log_api_exception=False)
                self._attr_volume_level = volume

    async def async_media_play(self) -> None:
        """Play whatever media is currently active."""
        await self._device.play(log_api_exception=False)

    async def async_media_pause(self) -> None:
        """Pause whatever media is currently active."""
        await self._device.pause(log_api_exception=False)
