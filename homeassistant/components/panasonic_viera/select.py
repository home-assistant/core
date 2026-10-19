"""Picture mode selection support for Panasonic Viera TVs."""

from typing import override

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.components.select import SelectEntity
from homeassistant.const import ATTR_MANUFACTURER, CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DEVICE_INFO,
    ATTR_MODEL_NUMBER,
    ATTR_UDN,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NUMBER,
    DOMAIN,
)
from .coordinator import PanasonicVieraConfigEntry, PanasonicVieraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PanasonicVieraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PAC picture mode selector once the TV reports support for it."""
    coordinator = config_entry.runtime_data
    config = config_entry.data
    device_info = config[ATTR_DEVICE_INFO]
    if device_info is None:
        return

    remove_listener: CALLBACK_TYPE | None = None

    @callback
    def async_discover_picture_mode() -> None:
        nonlocal remove_listener
        picture_modes = coordinator.remote.picture_mode_list
        if picture_modes is None:
            return
        if remove_listener is not None:
            remove_listener()
            remove_listener = None
        if picture_modes:
            async_add_entities(
                [
                    PanasonicVieraPictureModeEntity(
                        coordinator, config[CONF_NAME], device_info
                    )
                ]
            )

    if coordinator.remote.picture_mode_list is not None:
        async_discover_picture_mode()
        return

    # The TV was unreachable during setup: keep polling until it can be probed.
    remove_listener = coordinator.async_add_listener(async_discover_picture_mode)


class PanasonicVieraPictureModeEntity(
    CoordinatorEntity[PanasonicVieraCoordinator], SelectEntity
):
    """Representation of a Panasonic PAC picture mode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "picture_mode"

    def __init__(
        self,
        coordinator: PanasonicVieraCoordinator,
        name: str,
        device_info: dict[str, str],
    ) -> None:
        """Initialize the picture mode selector."""
        super().__init__(coordinator)
        self._remote = coordinator.remote
        self._attr_unique_id = f"{device_info[ATTR_UDN]}_picture_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_info[ATTR_UDN])},
            manufacturer=device_info.get(ATTR_MANUFACTURER, DEFAULT_MANUFACTURER),
            model=device_info.get(ATTR_MODEL_NUMBER, DEFAULT_MODEL_NUMBER),
            name=name,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the TV is on and exposes its picture modes."""
        return self._remote.available and self._remote.state is MediaPlayerState.ON

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current PAC picture mode."""
        return self._remote.picture_mode

    @property
    @override
    def options(self) -> list[str]:
        """Return the picture modes exposed by PAC."""
        return self._remote.picture_mode_list or []

    @override
    async def async_select_option(self, option: str) -> None:
        """Select a PAC picture mode."""
        await self._remote.async_select_picture_mode(option)
        self.coordinator.async_update_listeners()
