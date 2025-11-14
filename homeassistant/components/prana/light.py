"""Light platform for Prana integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PranaLightType
from .coordinator import PranaCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


class PranaSendBrightness:
    """Helper to send brightness commands to the device."""

    def __init__(self, coordinator: PranaCoordinator) -> None:
        """Initialize brightness sender."""
        self.coordinator = coordinator

    async def send_brightness(self, brightness: int) -> None:
        """Send brightness level (0-6 mapped) to the device."""
        mapping = {0: 0, 1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 32}
        brightness = mapping.get(brightness, 0)
        request_data = {"brightness": brightness}
        _LOGGER.debug("Setting brightness to %s", brightness)
        async with (
            ClientSession() as session,
            session.post(
                f"http://{self.coordinator.entry.data.get('host')}:80/setBrightness",
                json=request_data,
            ) as resp,
        ):
            if resp.status != 200:
                raise HomeAssistantError(f"HTTP {resp.status}")


class PranaBrightness(LightEntity):
    """Representation of the Prana display brightness as a light entity."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_unique_id: str
    _attr_icon = "mdi:brightness-7"

    def __init__(
        self,
        unique_id: str,
        name: str,
        coordinator: PranaCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize brightness entity."""
        self._attr_unique_id = unique_id
        self._attr_translation_key = "brightness"
        self.coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Prana Device"),
            manufacturer="Prana",
            model="PRANA RECUPERATOR",
        )

    @property
    def is_on(self) -> bool:
        """Return True if brightness > 0."""
        if self.coordinator.data:
            brightness = self.coordinator.data.get(PranaLightType.BRIGHTNESS, 0)
            return brightness > 0
        return False

    @property
    def brightness(self) -> int | None:
        """Return mapped HA brightness (0-255)."""
        if self.coordinator.data:
            device_brightness = self.coordinator.data.get(PranaLightType.BRIGHTNESS, 0)
            if device_brightness == 0:
                return 0
            return int(((device_brightness - 1) / 5) * 212 + 43)
        return 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on / adjust brightness."""
        brightness = kwargs.get("brightness", 255)
        if brightness == 0:
            device_brightness = 1
        else:
            device_brightness = max(1, min(6, round((brightness - 1) / 254 * 5) + 1))
        sender = PranaSendBrightness(self.coordinator)
        await sender.send_brightness(device_brightness)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (set brightness to 0)."""
        sender = PranaSendBrightness(self.coordinator)
        await sender.send_brightness(0)
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when added."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        """Return availability based on coordinator success."""
        return self.coordinator.last_update_success


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana light entities from a config entry."""
    _LOGGER.info("Setting up Prana light entities")
    coordinator: PranaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PranaBrightness(
                unique_id=f"{entry.entry_id}-brightness",
                name="Display Brightness",
                coordinator=coordinator,
                entry=entry,
            )
        ]
    )
