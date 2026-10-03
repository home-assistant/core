"""DRIQON on/off switch platform."""
from __future__ import annotations

import logging
from typing import Any, Literal

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import DriqonConfigEntry, DriqonRuntimeData
from .api import DriqonApiError, DriqonAuthorizationError
from .const import DOMAIN
from .entity import DriqonEntity
from .types import Device

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DriqonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create an entity for each device advertising the on/off switch capability."""
    runtime: DriqonRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator
    added_devices: set[str] = set()

    def add_supported_devices() -> None:
        new_entities: list[DriqonSwitch] = []
        for device in coordinator.data.values():
            if (
                _supports_on_off(device)
                and device["device_id"] not in added_devices
            ):
                added_devices.add(device["device_id"])
                new_entities.append(DriqonSwitch(coordinator, device))
        if new_entities:
            async_add_entities(new_entities)

    add_supported_devices()
    entry.async_on_unload(coordinator.async_add_listener(add_supported_devices))


def _supports_on_off(device: Device) -> bool:
    """Return whether a device advertises the current DRIQON switch capability."""
    return any(
        capability.get("name") == "on_off"
        and capability.get("platform") == "switch"
        for capability in device.get("capabilities", [])
    )


class DriqonSwitch(DriqonEntity, SwitchEntity):
    """A DRIQON switch whose commands use the permission-checked cloud API."""

    def __init__(self, coordinator: DriqonCoordinator, device: Device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self.device_id}_on_off"

    @property
    def is_on(self) -> bool:
        """Return the last state reported by the DRIQON backend."""
        device = self.coordinator.data.get(self.device_id)
        return bool(device and str(device.get("state", "")).upper() == "ON")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this device through the authenticated backend."""
        await self._async_command("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this device through the authenticated backend."""
        await self._async_command("off")

    async def _async_command(self, command: Literal["on", "off"]) -> None:
        """Respect shared-device roles and report failed cloud commands."""
        device = self.coordinator.data.get(self.device_id)
        if not device:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_unavailable"
            )
        if device.get("permission") not in {"owner", "control", "admin"}:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="control_not_allowed"
            )
        try:
            await self.coordinator.api.command(self.device_id, command)
        except DriqonAuthorizationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="control_not_allowed"
            ) from err
        except DriqonApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        try:
            await self.coordinator.async_request_refresh()
        except UpdateFailed:
            # The command succeeded. The regular coordinator poll will refresh state.
            _LOGGER.debug("DRIQON command succeeded; immediate state refresh failed")
