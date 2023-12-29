"""Govee Light."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from govee_local_api import GoveeDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SCAN_INTERVAL
from .capability import (
    GOVEE_COORDINATORS_MAPPER,
    GOVEE_DEVICE_CAPABILITIES,
    GoveeLightCapabilities,
)
from .const import DOMAIN, MANUFACTURER
from .coordinator import GoveeLocalApiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Govee light setup."""

    entry_id = config_entry.entry_id
    coordinator: GoveeLocalApiCoordinator = hass.data.setdefault(DOMAIN, {}).get(
        entry_id, None
    )

    def add_device(coordinator: GoveeLocalApiCoordinator, device: GoveeDevice):
        async_add_entities([GoveeLight(coordinator, device)])

    if not coordinator:
        coordinator = GoveeLocalApiCoordinator(
            hass=hass,
            config_entry=config_entry,
            async_add_entities=add_device,
            scan_interval=SCAN_INTERVAL,
            logger=_LOGGER,
        )

        hass.data.setdefault(DOMAIN, {})[entry_id] = coordinator
        await coordinator.start()

    await coordinator.async_config_entry_first_refresh()


class GoveeLight(CoordinatorEntity, LightEntity):
    """Govee Light."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoveeLocalApiCoordinator,
        device: GoveeDevice,
    ) -> None:
        """Govee Light constructor."""

        super(CoordinatorEntity, self).__init__(coordinator)

        self._coordinator = coordinator
        self._device = device
        self._device.set_update_callback(self._update_callback)

        capabilities: set[GoveeLightCapabilities] = GOVEE_DEVICE_CAPABILITIES.get(
            device.sku, set()
        )

        self._attr_unique_id: str = device.fingerprint
        self.entry_id = f"{device.sku}_{device.fingerprint}"

        color_modes = set()
        if GoveeLightCapabilities.COLOR_RGB in capabilities:
            color_modes.add(ColorMode.RGB)
        if GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE in capabilities:
            color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_max_color_temp_kelvin = 9000
            self._attr_min_color_temp_kelvin = 2000
        if GoveeLightCapabilities.BRIGHTNESS in capabilities:
            color_modes.add(ColorMode.BRIGHTNESS)

        if len(color_modes) == 0:
            color_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes: set[ColorMode] | set[str] = color_modes

    @property
    def name(self) -> str:
        """Name of the entity."""
        return self._device.sku

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self._device.on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return int((self._device.brightness / 100.0) * 255.0)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._device.temperature_color

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color."""
        return self._device.rgb_color

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode."""
        if (
            self._device.temperature_color is not None
            and self._device.temperature_color > 0
        ):
            return ColorMode.COLOR_TEMP
        if self._device.rgb_color is not None and any(self._device.rgb_color):
            return ColorMode.RGB
        return next((x for x in self._attr_supported_color_modes), ColorMode.ONOFF)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if not self.is_on or not kwargs:
            await self._coordinator.turn_on(self._device)

        if ATTR_BRIGHTNESS in kwargs:
            brightness: int = int((float(kwargs[ATTR_BRIGHTNESS]) / 255.0) * 100.0)
            await self._coordinator.set_brightness(self._device, brightness)

        if ATTR_RGB_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGB
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            await self._coordinator.set_rgb_color(self._device, red, green, blue)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            temperature: float = kwargs[ATTR_COLOR_TEMP_KELVIN]

            converter: Callable[..., Any] = GOVEE_COORDINATORS_MAPPER.get(
                GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE, lambda x: x
            )

            await self._coordinator.set_temperature(
                self._device, converter(temperature)
            )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._coordinator.turn_off(self._device)
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
            manufacturer=MANUFACTURER,
            model=self._device.sku,
            connections={("mac", self._device.fingerprint)},
        )

    @callback
    def _update_callback(self, device: GoveeDevice) -> None:
        self.async_write_ha_state()
