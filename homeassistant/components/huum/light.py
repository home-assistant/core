"""Control for light."""

from __future__ import annotations

import logging

from huum.huum import Huum

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HuumLight(data.get("coordinator"), data.get("huum"), entry.entry_id)], True
    )


class HuumLight(CoordinatorEntity, LightEntity):
    """Representation of a light."""

    _attr_has_entity_name = True
    _attr_name = "Light"
    _attr_supported_color_modes = set(ColorMode.ONOFF)
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self, coordinator: CoordinatorEntity, huum: Huum, unique_id: str
    ) -> None:
        """Initialize the light."""
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_unique_id = f"{unique_id}_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name="Huum sauna",
            manufacturer="Huum",
            model="UKU WiFi",
            serial_number=coordinator.data.sauna_name,
        )

        self._huum = huum
        self._coordinator = coordinator

    @property
    def is_on(self) -> bool | None:
        """Return the current light status."""
        return self._coordinator.data.light == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if not self.is_on:
            await self._toggle_light()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn device off."""
        if self.is_on:
            await self._toggle_light()

    async def _toggle_light(self) -> None:
        await self._huum.toggle_light()
