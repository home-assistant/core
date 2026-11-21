"""Represent conventional Dobiss NXT light outputs."""

from typing import Any, override

from dobiss_nxt import DobissError, Light

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import DOMAIN
from .coordinator import DobissConfigEntry, DobissCoordinator, DobissLightData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DobissConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the discovered light outputs."""
    async_add_entities(DobissLight(entry, light) for light in entry.runtime_data.lights)


class DobissLight(CoordinatorEntity[DobissCoordinator], LightEntity):
    """A light output with immediate feedback after accepted commands."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: DobissConfigEntry, light: Light) -> None:
        """Initialize a named light with a stable config-entry scoped identifier."""
        super().__init__(entry.runtime_data)
        self._key = light.key
        self._attr_unique_id = f"{entry.entry_id}_{light.key}"
        controller_id = dr.async_get_device_id_by_identifier(
            self.coordinator.hass,
            (DOMAIN, entry.entry_id),
            config_entry_id=entry.entry_id,
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{light.key}")},
            name=light.name,
            manufacturer="Dobiss",
            model="NXT output",
            via_device_id=controller_id,
        )
        mode = ColorMode.BRIGHTNESS if light.dimmable else ColorMode.ONOFF
        self._attr_color_mode = mode
        self._attr_supported_color_modes = {mode}

    @property
    @override
    def available(self) -> bool:
        """Missing output state must not be represented as off."""
        return super().available and self._key in self.coordinator.data

    @property
    def _light(self) -> DobissLightData:
        """Return the current output data."""
        return self.coordinator.data[self._key]

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the output is enabled."""
        return bool(self._light.value)

    @property
    @override
    def brightness(self) -> int | None:
        """Convert the percentage to Home Assistant brightness."""
        value = self._light.value
        if not self._light.light.dimmable:
            return None
        if value == 0:
            return 0
        return value_to_brightness((1, 100), value)

    async def _async_set_light(self, on: bool, brightness: int | None = None) -> None:
        try:
            await self.coordinator.async_set_light(
                self._light.light, on=on, brightness=brightness
            )
        except DobissError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, optionally setting a dimmer percentage."""
        brightness = None
        if ATTR_BRIGHTNESS in kwargs and self._light.light.dimmable:
            brightness = max(
                1, round(brightness_to_value((1, 100), kwargs[ATTR_BRIGHTNESS]))
            )
        await self._async_set_light(True, brightness)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the output."""
        await self._async_set_light(False)
