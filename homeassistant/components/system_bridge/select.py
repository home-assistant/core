"""Support for System Bridge selects."""

from typing import override

from systembridgeconnector.models.modules.audio import AudioDevice
from systembridgeconnector.models.system_control import PowerProfileRequest

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeAudioEntity, SystemBridgeEntity, unique_names

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge selects based on a config entry."""
    coordinator = entry.runtime_data
    audio_input_added = False
    power_profile_added = False

    @callback
    def _async_add_audio_input() -> None:
        """Add the audio input select once the backend reports audio."""
        nonlocal audio_input_added
        if audio_input_added or coordinator.data.audio is None:
            return
        audio_input_added = True
        async_add_entities(
            [SystemBridgeAudioInputSelect(coordinator, entry.data[CONF_PORT])]
        )

    _async_add_audio_input()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_audio_input))

    # Only systems with power profiles report one, and the daemon providing
    # them can start after System Bridge
    @callback
    def _async_add_power_profile() -> None:
        nonlocal power_profile_added
        if power_profile_added or (system := coordinator.data.system) is None:
            return
        if system.power_profile is None:
            return
        power_profile_added = True
        async_add_entities(
            [
                SystemBridgePowerProfileSelect(
                    coordinator, entry.data[CONF_PORT], "power_profile"
                )
            ]
        )

    _async_add_power_profile()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_power_profile))


class SystemBridgePowerProfileSelect(SystemBridgeEntity, SelectEntity):
    """Define a System Bridge power profile select."""

    _attr_translation_key = "power_profile"

    @property
    @override
    def available(self) -> bool:
        """Return True if the system reports a power profile."""
        return (
            super().available
            and (system := self.coordinator.data.system) is not None
            and system.power_profile is not None
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the active power profile."""
        if (system := self.coordinator.data.system) is None:
            return None
        return system.power_profile

    @property
    @override
    def options(self) -> list[str]:
        """Return the power profiles that can be switched to."""
        if (system := self.coordinator.data.system) is None:
            return []
        return system.power_profiles

    @override
    async def async_select_option(self, option: str) -> None:
        """Switch the power profile."""
        await self._async_system_control(
            self.coordinator.websocket_client.set_power_profile(
                PowerProfileRequest(profile=option)
            )
        )


class SystemBridgeAudioInputSelect(SystemBridgeAudioEntity, SelectEntity):
    """Define a System Bridge select for the default audio input."""

    _attr_translation_key = "audio_input"

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, api_port, "audio_input")

    @property
    def _inputs(self) -> list[AudioDevice]:
        """Return every audio input."""
        if (audio := self.coordinator.data.audio) is None:
            return []
        return audio.inputs

    @property
    @override
    def _device(self) -> AudioDevice | None:
        """Return the default input, following it when it changes."""
        return next((device for device in self._inputs if device.default), None)

    @property
    @override
    def available(self) -> bool:
        """Return True while there are inputs, even when none is the default."""
        return self.coordinator.last_update_success and bool(self._inputs)

    @property
    def _names(self) -> dict[str, str]:
        """Return each input's option, by ID."""
        return unique_names((device.id, device.name) for device in self._inputs)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the default input's option."""
        if (device := self._device) is None:
            return None
        return self._names[device.id]

    @property
    @override
    def options(self) -> list[str]:
        """Return the options for the inputs that can be made the default."""
        return list(self._names.values())

    @override
    async def async_select_option(self, option: str) -> None:
        """Make an input the default."""
        names = self._names
        device = next(device for device in self._inputs if names[device.id] == option)
        await self._async_audio_control(device, default=True)
