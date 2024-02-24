"""Support for Android IP Webcam settings."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pydroid_ipcam import PyDroidIPCam

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AndroidIPCamDataUpdateCoordinator
from .entity import AndroidIPCamBaseEntity


@dataclass(frozen=True)
class AndroidIPWebcamSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    on_func: Callable[[PyDroidIPCam], Coroutine[Any, Any, bool]]
    off_func: Callable[[PyDroidIPCam], Coroutine[Any, Any, bool]]


@dataclass(frozen=True)
class AndroidIPWebcamSwitchEntityDescription(
    SwitchEntityDescription, AndroidIPWebcamSwitchEntityDescriptionMixin
):
    """Entity description class for Android IP Webcam switches."""


SWITCH_TYPES: tuple[AndroidIPWebcamSwitchEntityDescription, ...] = (
    AndroidIPWebcamSwitchEntityDescription(
        key="exposure_lock",
        name="Exposure lock",
        icon="mdi:camera",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("exposure_lock", True),
        off_func=lambda ipcam: ipcam.change_setting("exposure_lock", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="ffc",
        name="Front-facing camera",
        icon="mdi:camera-front-variant",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("ffc", True),
        off_func=lambda ipcam: ipcam.change_setting("ffc", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="focus",
        name="Focus",
        icon="mdi:image-filter-center-focus",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.focus(activate=True),
        off_func=lambda ipcam: ipcam.focus(activate=False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="gps_active",
        name="GPS active",
        icon="mdi:crosshairs-gps",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("gps_active", True),
        off_func=lambda ipcam: ipcam.change_setting("gps_active", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="motion_detect",
        name="Motion detection",
        icon="mdi:flash",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("motion_detect", True),
        off_func=lambda ipcam: ipcam.change_setting("motion_detect", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="night_vision",
        name="Night vision",
        icon="mdi:weather-night",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("night_vision", True),
        off_func=lambda ipcam: ipcam.change_setting("night_vision", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="overlay",
        name="Overlay",
        icon="mdi:monitor",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("overlay", True),
        off_func=lambda ipcam: ipcam.change_setting("overlay", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="torch",
        name="Torch",
        icon="mdi:white-balance-sunny",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.torch(activate=True),
        off_func=lambda ipcam: ipcam.torch(activate=False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="whitebalance_lock",
        name="White balance lock",
        icon="mdi:white-balance-auto",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.change_setting("whitebalance_lock", True),
        off_func=lambda ipcam: ipcam.change_setting("whitebalance_lock", False),
    ),
    AndroidIPWebcamSwitchEntityDescription(
        key="video_recording",
        name="Video recording",
        icon="mdi:record-rec",
        entity_category=EntityCategory.CONFIG,
        on_func=lambda ipcam: ipcam.record(record=True),
        off_func=lambda ipcam: ipcam.record(record=False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IP Webcam switches from config entry."""

    coordinator: AndroidIPCamDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    switch_types = [
        switch
        for switch in SWITCH_TYPES
        if switch.key in coordinator.cam.enabled_settings
    ]
    async_add_entities(
        [
            IPWebcamSettingSwitch(coordinator, description)
            for description in switch_types
        ]
    )


class IPWebcamSettingSwitch(AndroidIPCamBaseEntity, SwitchEntity):
    """Representation of a IP Webcam setting."""

    entity_description: AndroidIPWebcamSwitchEntityDescription

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
        description: AndroidIPWebcamSwitchEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return if settings is on or off."""
        return bool(self.cam.current_settings.get(self.entity_description.key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        await self.entity_description.on_func(self.cam)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self.entity_description.off_func(self.cam)
        await self.coordinator.async_request_refresh()
