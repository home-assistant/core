"""iNels light."""
from __future__ import annotations

from typing import Any, cast

from inelsmqtt.const import RFDAC_71B

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import COORDINATOR_LIST, DOMAIN, ICON_LIGHT
from .coordinator import InelsDeviceUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Inels lights from config entry."""
    coordinator_data: list[InelsDeviceUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ][COORDINATOR_LIST]

    async_add_entities(
        [
            InelsLight(device_coordinator)
            for device_coordinator in coordinator_data
            if device_coordinator.device.device_type == Platform.LIGHT
        ],
    )


class InelsLight(InelsBaseEntity, LightEntity):
    """Light class for HA."""

    def __init__(self, device_coordinator: InelsDeviceUpdateCoordinator) -> None:
        """Initialize a light."""
        super().__init__(device_coordinator=device_coordinator)
        self._device_control = self._device

        self._attr_supported_color_modes: set[ColorMode] = set()
        if self._device_control.inels_type is RFDAC_71B:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)

    def _refresh(self) -> None:
        """Refresh the device."""
        super()._refresh()
        self._device_control = self._device

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device_control.state > 0

    @property
    def icon(self) -> str | None:
        """Light icon."""
        return ICON_LIGHT

    @property
    def brightness(self) -> int | None:
        """Light brightness."""
        if self._device_control.inels_type is not RFDAC_71B:
            return None
        return cast(int, self._device_control.state * 2.55)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Light to turn off."""
        if not self._device_control:
            return

        transition = None

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION]) / 0.065
            print(transition)
        else:
            self.hass.async_add_executor_job(self._device_control.set_ha_value, 0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Light to turn on."""
        if not self._device_control:
            return

        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 2.55)
            brightness = min(brightness, 100)

            self.hass.async_add_executor_job(
                self._device_control.set_ha_value, brightness
            )
        else:
            self.hass.async_add_executor_job(self._device_control.set_ha_value, 100)
