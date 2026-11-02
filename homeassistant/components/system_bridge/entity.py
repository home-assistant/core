"""Base entity for the system bridge integration."""

from collections import Counter
from collections.abc import Callable, Iterable
from typing import override

from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.audio_control import AudioControl
from systembridgeconnector.models.display_control import DisplayControl
from systembridgeconnector.models.modules.audio import AudioDevice
from systembridgeconnector.models.modules.displays import Display, DisplayPowerState

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AUDIO_OUTPUT, DOMAIN
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator


class SystemBridgeEntity(CoordinatorEntity[SystemBridgeDataUpdateCoordinator]):
    """Defines a base System Bridge entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str | None = None,
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)

        system = coordinator.data.system
        assert system is not None

        self._hostname = system.hostname
        self._attr_unique_id = (
            f"{system.uuid}_{key}" if key is not None else system.uuid
        )
        self._configuration_url = f"http://{self._hostname}:{api_port}/settings"
        self._mac_address = system.mac_address
        self._uuid = system.uuid
        self._version = system.version

        self._attr_device_info = DeviceInfo(
            configuration_url=self._configuration_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
            identifiers={(DOMAIN, self._uuid)},
            name=self._hostname,
            sw_version=self._version,
        )


class SystemBridgeDisplayEntity(SystemBridgeEntity):
    """Defines a System Bridge entity that controls a display."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str,
        display_id: str,
    ) -> None:
        """Initialize the System Bridge display entity."""
        super().__init__(coordinator, api_port, f"display_{display_id}_{key}")
        self._display_id = display_id
        self._attr_translation_placeholders = {"display_id": display_id}

    @property
    def _display(self) -> Display | None:
        """Return the display, if it is still connected."""
        return next(
            (
                display
                for display in self.coordinator.data.displays
                if display.id == self._display_id
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the display is connected."""
        return super().available and self._display is not None

    async def _async_display_control(
        self,
        brightness: float | None = None,
        power_state: DisplayPowerState | None = None,
    ) -> None:
        """Set the display's brightness or power state."""
        try:
            response = await self.coordinator.websocket_client.display_control(
                DisplayControl(
                    id=self._display_id,
                    brightness=brightness,
                    power_state=power_state,
                )
            )
        except ConnectionClosedException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e
        if response.type == EventType.ERROR:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="display_control_failed",
                translation_placeholders={
                    "display_id": self._display_id,
                    "error": response.message or "",
                },
            )


class SystemBridgeAudioEntity(SystemBridgeEntity):
    """Defines a System Bridge entity that controls an audio device."""

    @property
    def _device(self) -> AudioDevice | None:
        """Return the audio device, if there is one."""
        raise NotImplementedError

    @property
    @override
    def available(self) -> bool:
        """Return True if the audio device is connected."""
        return super().available and self._device is not None

    async def _async_audio_control(
        self,
        device: AudioDevice,
        volume: float | None = None,
        muted: bool | None = None,
        default: bool | None = None,
    ) -> None:
        """Set an audio device's volume, mute state or make it the default."""
        try:
            response = await self.coordinator.websocket_client.audio_control(
                AudioControl(id=device.id, volume=volume, muted=muted, default=default)
            )
        except ConnectionClosedException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e
        if response.type == EventType.ERROR:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="audio_control_failed",
                translation_placeholders={
                    "name": device.name,
                    "error": response.message or "",
                },
            )


class SystemBridgeAudioDeviceEntity(SystemBridgeAudioEntity):
    """Defines a System Bridge entity for one audio output or input."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str,
        kind: str,
        device: AudioDevice,
    ) -> None:
        """Initialize the System Bridge audio device entity."""
        super().__init__(coordinator, api_port, key)
        self._kind = kind
        self._device_id = device.id
        self._attr_translation_placeholders = {"name": device.name}

    @property
    @override
    def _device(self) -> AudioDevice | None:
        """Return the audio device, if it is still connected."""
        if (audio := self.coordinator.data.audio) is None:
            return None
        devices = audio.outputs if self._kind == AUDIO_OUTPUT else audio.inputs
        return next(
            (device for device in devices if device.id == self._device_id), None
        )


@callback
def async_add_new_audio_devices(
    entry: SystemBridgeConfigEntry,
    kind: str,
    add: Callable[[list[AudioDevice]], None],
    include: Callable[[AudioDevice], bool] = lambda _: True,
) -> None:
    """Call add with the outputs or inputs not seen before, now and on updates."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _async_check() -> None:
        if (audio := coordinator.data.audio) is None:
            return
        devices = audio.outputs if kind == AUDIO_OUTPUT else audio.inputs
        # Only devices that are included count as seen, so one that later
        # reports what it was missing still gets its entity
        if new_devices := [
            device for device in devices if device.id not in known and include(device)
        ]:
            known.update(device.id for device in new_devices)
            add(new_devices)

    _async_check()
    entry.async_on_unload(coordinator.async_add_listener(_async_check))


def unique_names(
    items: Iterable[tuple[str, str]], reserved: Iterable[str] = ()
) -> dict[str, str]:
    """Map each ID to its name, adding the ID to names that repeat or are reserved."""
    items = list(items)
    reserved = list(reserved)
    while True:
        # Adding an ID can match another device's name, so repeat until unique
        counts = Counter(name for _, name in items)
        counts.update(reserved)
        if all(counts[name] == 1 for _, name in items):
            return dict(items)
        items = [
            (item_id, name if counts[name] == 1 else f"{name} ({item_id})")
            for item_id, name in items
        ]
