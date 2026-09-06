"""Vizio SmartCast Device support."""

from typing import Any, cast, override

from vizaio import AppConfig, AppRecord, RemoteKey
from vizaio.apps import (
    APP_HOME,
    NO_APP_RUNNING,
    UNKNOWN_APP,
    find_app_name,
    is_app_input,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DATA_APPS
from .const import (
    CONF_ADDITIONAL_CONFIGS,
    CONF_APP_ID,
    CONF_APPS,
    CONF_CONFIG,
    CONF_MESSAGE,
    CONF_NAME_SPACE,
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
from .coordinator import VizioAppsDataUpdateCoordinator, VizioConfigEntry
from .entity import VizioEntity
from .helpers import async_device_command

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Vizio media player entry."""
    device_class = config_entry.data[CONF_DEVICE_CLASS]

    entity = VizioDevice(
        config_entry,
        device_class,
        hass.data.get(DATA_APPS) if device_class == MediaPlayerDeviceClass.TV else None,
    )

    async_add_entities([entity])


def _app_config_from_conf(config: dict[str, Any]) -> AppConfig:
    """Convert a stored uppercase-key app config to a vizaio AppConfig."""
    return AppConfig(
        app_id=str(config[CONF_APP_ID]),
        name_space=int(config[CONF_NAME_SPACE]),
        message=config.get(CONF_MESSAGE),
    )


class VizioDevice(VizioEntity, MediaPlayerEntity):
    """Media Player implementation which performs REST requests to device."""

    _attr_name = None
    _current_input: str | None = None
    _current_app_config: AppConfig | None = None

    def __init__(
        self,
        config_entry: VizioConfigEntry,
        device_class: MediaPlayerDeviceClass,
        apps_coordinator: VizioAppsDataUpdateCoordinator | None,
    ) -> None:
        """Initialize Vizio device."""
        super().__init__(config_entry)

        self._config_entry = config_entry
        self._apps_coordinator = apps_coordinator
        self._attr_sound_mode_list = []
        self._available_inputs: list[str] = []
        self._available_apps: list[str] = []

        self._all_apps = apps_coordinator.data if apps_coordinator else None
        self._additional_app_configs = config_entry.data.get(CONF_APPS, {}).get(
            CONF_ADDITIONAL_CONFIGS, []
        )
        if apps_coordinator:
            self._device.set_app_catalog(apps_coordinator.data)
            self._device.set_app_availability(apps_coordinator.availability)
        self._max_volume = float(self._device.profile.max_volume)

        # Entity class attributes that will change with each update (we only include
        # the ones that are initialized differently from the defaults)
        self._attr_supported_features = SUPPORTED_COMMANDS[device_class]
        self._attr_device_class = device_class

    @property
    def _volume_step(self) -> int:
        """Return the configured volume step."""
        return cast(
            int, self._config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        )

    @property
    def _conf_apps(self) -> dict[str, Any]:
        """Return the configured app filter options."""
        return cast("dict[str, Any]", self._config_entry.options.get(CONF_APPS, {}))

    def _apps_list(self, apps: list[str]) -> list[str]:
        """Return process apps list based on configured filters."""
        if self._conf_apps.get(CONF_INCLUDE):
            return [app for app in apps if app in self._conf_apps[CONF_INCLUDE]]

        if self._conf_apps.get(CONF_EXCLUDE):
            return [app for app in apps if app not in self._conf_apps[CONF_EXCLUDE]]

        return apps

    @callback
    @override
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

        # Audio settings. Volume and mute come from the collection when it
        # carries them, and from the coordinator's individual reads when it
        # does not - some firmware omits them from the collection.
        volume: int | None
        if data.audio_settings and VIZIO_VOLUME in data.audio_settings:
            volume = int(data.audio_settings[VIZIO_VOLUME].value)
        else:
            volume = data.volume
        self._attr_volume_level = (
            None if volume is None else float(volume) / self._max_volume
        )

        if data.audio_settings and VIZIO_MUTE in data.audio_settings:
            self._attr_is_volume_muted = (
                str(data.audio_settings[VIZIO_MUTE].value).lower() == VIZIO_MUTE_ON
            )
        else:
            self._attr_is_volume_muted = data.is_muted

        if data.audio_settings:
            if VIZIO_SOUND_MODE in data.audio_settings:
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.SELECT_SOUND_MODE
                )
                self._attr_sound_mode = str(data.audio_settings[VIZIO_SOUND_MODE].value)
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
            and any(is_app_input(name) for name in self._available_inputs)
        ):
            all_apps = self._all_apps or ()
            self._available_apps = self._apps_list([app.name for app in all_apps])
            self._current_app_config = data.current_app_config
            app_name = find_app_name(
                self._current_app_config,
                [APP_HOME, *all_apps, *self._additional_app_records()],
                availability=(
                    self._apps_coordinator.availability
                    if self._apps_coordinator
                    else ()
                ),
            )
            # find_app_name returns None on a catalog miss; the app_name state
            # attribute contract expects the UNKNOWN_APP sentinel instead
            if app_name == NO_APP_RUNNING:
                self._attr_app_name = None
            elif app_name is None:
                self._attr_app_name = UNKNOWN_APP
            else:
                self._attr_app_name = app_name

        super()._handle_coordinator_update()

    def _get_additional_app_names(self) -> list[str]:
        """Return list of additional apps that were included in configuration.yaml."""
        return [
            additional_app["name"] for additional_app in self._additional_app_configs
        ]

    def _additional_app_records(self) -> list[AppRecord]:
        """Return AppRecords for additional apps from configuration.yaml."""
        return [
            AppRecord(
                name=app["name"],
                country=("*",),
                config=(_app_config_from_conf(app[CONF_CONFIG]),),
            )
            for app in self._additional_app_configs
        ]

    async def async_update_setting(
        self, setting_type: str, setting_name: str, new_value: int | str
    ) -> None:
        """Update a setting when update_setting service is called."""
        await async_device_command(
            self._device.set_setting(setting_type, setting_name, new_value)
        )

    async def async_send_text(self, text: str) -> None:
        """Type text into the focused on-screen field when send_text is called."""
        await async_device_command(self._device.send_text(text))

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()

        # Process initial coordinator data
        self._handle_coordinator_update()

        async def _async_write_state(*_: Any) -> None:
            self._handle_coordinator_update()

        self.async_on_remove(self._config_entry.add_update_listener(_async_write_state))

        if not (apps_coordinator := self._apps_coordinator):
            return

        # Register callback for app list updates if device is a TV
        @callback
        def apps_list_update() -> None:
            """Update list of all apps."""
            self._all_apps = apps_coordinator.data
            self._device.set_app_catalog(apps_coordinator.data)
            self._device.set_app_availability(apps_coordinator.availability)
            self.async_write_ha_state()

        self.async_on_remove(apps_coordinator.async_add_listener(apps_list_update))

    @property
    @override
    def source(self) -> str | None:
        """Return current input of the device."""
        if (
            self._attr_app_name is not None
            and self._current_input is not None
            and is_app_input(self._current_input)
        ):
            return self._attr_app_name

        return self._current_input

    @property
    @override
    def source_list(self) -> list[str]:
        """Return list of available inputs of the device."""
        # If Smartcast app is in input list, and the app list has been retrieved,
        # show the combination with, otherwise just return inputs
        if self._available_apps:
            return [
                *(
                    _input
                    for _input in self._available_inputs
                    if not is_app_input(_input)
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
    @override
    # pylint: disable-next=home-assistant-return-type
    def app_id(self) -> dict[str, Any] | None:  # type: ignore[override]
        """Return the app config of the current app if it is unknown by vizaio.

        Documented way for users to obtain app configs for additional_configs;
        intentionally returns a dict instead of the app ID string.
        """
        if self._current_app_config and self.source == UNKNOWN_APP:
            return {
                CONF_APP_ID: self._current_app_config.app_id,
                CONF_NAME_SPACE: self._current_app_config.name_space,
                CONF_MESSAGE: self._current_app_config.message,
            }

        return None

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        if sound_mode not in (self._attr_sound_mode_list or ()):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_mode",
                translation_placeholders={"sound_mode": sound_mode},
            )
        await async_device_command(
            self._device.set_setting(VIZIO_AUDIO_SETTINGS, VIZIO_SOUND_MODE, sound_mode)
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await async_device_command(self._device.power_on())

    @override
    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await async_device_command(self._device.power_off())

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await async_device_command(self._device.mute())
            self._attr_is_volume_muted = True
        else:
            await async_device_command(self._device.unmute())
            self._attr_is_volume_muted = False

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous channel command."""
        await async_device_command(self._device.send_key(RemoteKey.CH_DOWN))

    @override
    async def async_media_next_track(self) -> None:
        """Send next channel command."""
        await async_device_command(self._device.send_key(RemoteKey.CH_UP))

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source in self._available_inputs:
            await async_device_command(self._device.set_input(source))
        elif source in self._get_additional_app_names():
            await async_device_command(
                self._device.launch_app_config(
                    _app_config_from_conf(
                        next(
                            app[CONF_CONFIG]
                            for app in self._additional_app_configs
                            if app["name"] == source
                        )
                    )
                )
            )
        elif source in self._available_apps:
            await async_device_command(self._device.launch_app(source))
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )

    @override
    async def async_volume_up(self) -> None:
        """Increase volume of the device."""
        await async_device_command(self._device.volume_up(steps=self._volume_step))

        if self._attr_volume_level is not None:
            self._attr_volume_level = min(
                1.0, self._attr_volume_level + self._volume_step / self._max_volume
            )

    @override
    async def async_volume_down(self) -> None:
        """Decrease volume of the device."""
        await async_device_command(self._device.volume_down(steps=self._volume_step))

        if self._attr_volume_level is not None:
            self._attr_volume_level = max(
                0.0, self._attr_volume_level - self._volume_step / self._max_volume
            )

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await async_device_command(
            self._device.set_volume(round(volume * self._max_volume))
        )
        self._attr_volume_level = volume

    @override
    async def async_media_play(self) -> None:
        """Play whatever media is currently active."""
        await async_device_command(self._device.send_key(RemoteKey.PLAY))

    @override
    async def async_media_pause(self) -> None:
        """Pause whatever media is currently active."""
        await async_device_command(self._device.send_key(RemoteKey.PAUSE))
