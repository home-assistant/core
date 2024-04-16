"""Switch platform for motionEye."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from motioneye_client.client import MotionEyeClient
from motioneye_client.const import (
    KEY_MOTION_DETECTION,
    KEY_MOVIES,
    KEY_STILL_IMAGES,
    KEY_TEXT_OVERLAY,
    KEY_UPLOAD_ENABLED,
    KEY_VIDEO_STREAMING,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MotionEyeEntity, get_camera_from_cameras, listen_for_new_cameras
from .const import CONF_CLIENT, CONF_COORDINATOR, DOMAIN, TYPE_MOTIONEYE_SWITCH_BASE

MOTIONEYE_SWITCHES = [
    SwitchEntityDescription(
        key=KEY_MOTION_DETECTION,
        translation_key="motion_detection",
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key=KEY_TEXT_OVERLAY,
        translation_key="text_overlay",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key=KEY_VIDEO_STREAMING,
        translation_key="video_streaming",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key=KEY_STILL_IMAGES,
        translation_key="still_images",
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key=KEY_MOVIES,
        translation_key="movies",
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key=KEY_UPLOAD_ENABLED,
        translation_key="upload_enabled",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback
    def camera_add(camera: dict[str, Any]) -> None:
        """Add a new motionEye camera."""
        async_add_entities(
            [
                MotionEyeSwitch(
                    entry.entry_id,
                    camera,
                    entry_data[CONF_CLIENT],
                    entry_data[CONF_COORDINATOR],
                    entry.options,
                    entity_description,
                )
                for entity_description in MOTIONEYE_SWITCHES
            ]
        )

    listen_for_new_cameras(hass, entry, camera_add)


class MotionEyeSwitch(MotionEyeEntity, SwitchEntity):
    """MotionEyeSwitch switch class."""

    def __init__(
        self,
        config_entry_id: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, str],
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            config_entry_id,
            f"{TYPE_MOTIONEYE_SWITCH_BASE}_{entity_description.key}",
            camera,
            client,
            coordinator,
            options,
            entity_description,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return bool(
            self._camera and self._camera.get(self.entity_description.key, False)
        )

    async def _async_send_set_camera(self, value: bool) -> None:
        """Set a switch value."""

        # Fetch the very latest camera config to reduce the risk of updating with a
        # stale configuration.
        camera = await self._client.async_get_camera(self._camera_id)
        if camera:
            camera[self.entity_description.key] = value
            await self._client.async_set_camera(self._camera_id, camera)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_send_set_camera(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_send_set_camera(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
        super()._handle_coordinator_update()
