"""Support for Blink Motion detection switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_BRAND, DOMAIN, TYPE_CAMERA_ARMED
from .coordinator import BlinkConfigEntry, BlinkUpdateCoordinator

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key=TYPE_CAMERA_ARMED,
        translation_key="camera_motion",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BlinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blink switches."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        BlinkSwitch(coordinator, camera, description)
        for camera in coordinator.api.cameras
        for description in SWITCH_TYPES
    )


class BlinkSwitch(CoordinatorEntity[BlinkUpdateCoordinator], SwitchEntity):
    """Representation of a Blink motion detection switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlinkUpdateCoordinator,
        camera,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._camera = coordinator.api.cameras[camera]
        self.entity_description = description
        serial = self._camera.serial
        self._attr_unique_id = f"{serial}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            serial_number=serial,
            name=camera,
            manufacturer=DEFAULT_BRAND,
            model=self._camera.camera_type,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self._camera.async_arm(True)

        except TimeoutError as er:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_arm_motion",
            ) from er

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self._camera.async_arm(False)

        except TimeoutError as er:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_disarm_motion",
            ) from er

        await self.coordinator.async_refresh()

    @property
    def is_on(self) -> bool:
        """Return if Camera Motion is enabled."""
        return self._camera.motion_enabled
