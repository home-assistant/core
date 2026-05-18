"""Light platform for the Lepro integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoproConfigEntry
from .const import DOMAIN
from .coordinator import LoproCoordinator

_LOGGER = logging.getLogger(__name__)

# Color temperature range supported by Lepro devices (in Kelvin)
MIN_COLOR_TEMP_KELVIN = 2700
MAX_COLOR_TEMP_KELVIN = 6500


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoproConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lepro lights from a config entry, with dynamic device discovery."""
    coordinator = entry.runtime_data
    known_dids: set[int] = set()

    def _check_for_new_devices() -> None:
        new_dids = set(coordinator.data) - known_dids
        if new_dids:
            known_dids.update(new_dids)
            async_add_entities(LoproLight(coordinator, did) for did in new_dids)

    entry.async_on_unload(coordinator.async_add_listener(_check_for_new_devices))
    _check_for_new_devices()


class LoproLight(CoordinatorEntity[LoproCoordinator], LightEntity):
    """Representation of a Lepro smart light device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN

    def __init__(self, coordinator: LoproCoordinator, did: int) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self._did = did
        self._attr_unique_id = str(did)
        self._attr_is_on = False
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN
        self._attr_rgb_color = (255, 255, 255)

    @property
    def _device_data(self) -> dict[str, Any]:
        """Return raw device data from the coordinator."""
        return self.coordinator.data[self._did]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        data = self._device_data
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._did))},
            name=data["name"],
            manufacturer="Lepro",
            model=data.get("series"),
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added, immediately parse state if coordinator already has data."""
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    def _apply_device_state(self, data: dict[str, Any]) -> None:
        """Apply raw device state dict to entity attributes."""
        self._attr_is_on = bool(data["switch"])
        self._attr_brightness = round(data["brightness"] / 1000 * 255)
        temp = data["temp"]
        self._attr_color_temp_kelvin = (
            round(2700 + temp / 1000 * 3800) if temp > 0 else MIN_COLOR_TEMP_KELVIN
        )
        self._attr_color_mode = ColorMode.COLOR_TEMP

    @callback
    def _handle_coordinator_update(self) -> None:
        """Parse device state from coordinator data."""
        data = self.coordinator.data.get(self._did)
        if data is None:
            return
        self._apply_device_state(data)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch current state for this device via the single-device endpoint."""
        if not self.enabled:
            return
        try:
            data = await self.coordinator.client.async_get_device_state(self._did)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch state for device %s", self._did)
            return
        self._apply_device_state(data)
        if self.coordinator.data is not None:
            self.coordinator.data[self._did].update(data)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light, optionally setting color, color temperature, or brightness."""
        if ATTR_RGB_COLOR in kwargs:
            rgb: tuple[int, int, int] = kwargs[ATTR_RGB_COLOR]
            await self.coordinator.client.async_set_color(self._did, rgb)
            self._attr_rgb_color = rgb
            self._attr_color_mode = ColorMode.RGB
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin: int = kwargs[ATTR_COLOR_TEMP_KELVIN]
            await self.coordinator.client.async_set_color_temp(self._did, kelvin)
            self._attr_color_temp_kelvin = kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif ATTR_BRIGHTNESS in kwargs:
            brightness_pct = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            await self.coordinator.client.async_set_brightness(
                self._did, brightness_pct
            )
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            await self.coordinator.client.async_turn_on(self._did)

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.client.async_turn_off(self._did)
        self._attr_is_on = False
        self.async_write_ha_state()
