"""Fully Kiosk Browser light entity for controlling screen brightness & on/off."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser light."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities([FullyLightEntity(coordinator)], False)


class FullyLightEntity(FullyKioskEntity, LightEntity):
    """Representation of a Fully Kiosk Browser light."""

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the light (screen) entity."""
        super().__init__(coordinator)

        self._attr_name = "Screen"
        self._attr_unique_id = f"{coordinator.data['deviceID']}-screen"
        self._attr_supported_features = SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool | None:
        """Return if the screen is on."""
        if self.coordinator.data.get("screenOn") is not None:
            return bool(self.coordinator.data["screenOn"])
        return None

    @property
    def brightness(self) -> int:
        """Return the screen brightness."""
        return int(self.coordinator.data["screenBrightness"])

    async def async_turn_on(self, **kwargs: dict[str, Any]) -> None:
        """Turn on the screen."""
        await self.coordinator.fully.screenOn()
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            await self.coordinator.async_refresh()
            return
        if brightness != self.coordinator.data["screenBrightness"]:
            await self.coordinator.fully.setScreenBrightness(brightness)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: dict[str, Any]) -> None:
        """Turn off the screen."""
        await self.coordinator.fully.screenOff()
        await self.coordinator.async_refresh()
