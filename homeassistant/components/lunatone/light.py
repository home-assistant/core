"""Platform for Lunatone light integration."""

from __future__ import annotations

import asyncio
from typing import Any

from lunatone_rest_api_client import DALIBroadcast
from lunatone_rest_api_client.models import LineStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import DOMAIN
from .coordinator import (
    LunatoneConfigEntry,
    LunatoneDevicesDataUpdateCoordinator,
    LunatoneInfoDataUpdateCoordinator,
)

PARALLEL_UPDATES = 0
STATUS_UPDATE_DELAY = 0.04


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Light platform."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_devices = config_entry.runtime_data.coordinator_devices
    dali_line_broadcasts = config_entry.runtime_data.dali_line_broadcasts

    entities: list[LightEntity] = [
        LunatoneLineBroadcastLight(
            coordinator_info, coordinator_devices, dali_line_broadcast
        )
        for dali_line_broadcast in dali_line_broadcasts
    ]
    entities.extend(
        [
            LunatoneLight(
                coordinator_devices, device_id, coordinator_info.data.device.serial
            )
            for device_id in coordinator_devices.data
        ]
    )

    async_add_entities(entities)


class LunatoneLight(
    CoordinatorEntity[LunatoneDevicesDataUpdateCoordinator], LightEntity
):
    """Representation of a Lunatone light."""

    BRIGHTNESS_SCALE = (1, 100)

    _last_brightness = 255

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: LunatoneDevicesDataUpdateCoordinator,
        device_id: int,
        interface_serial_number: int,
    ) -> None:
        """Initialize a Lunatone light."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._interface_serial_number = interface_serial_number
        self._device = self.coordinator.data[self._device_id]
        self._attr_unique_id = f"{interface_serial_number}-device{device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        assert self.unique_id
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self._device.name,
            via_device=(
                DOMAIN,
                f"{self._interface_serial_number}-line{self._device.data.line}",
            ),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._device is not None

    @property
    def is_on(self) -> bool:
        """Return True if light is on."""
        return self._device is not None and self._device.is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return value_to_brightness(self.BRIGHTNESS_SCALE, self._device.brightness)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._device is not None and self._device.is_dimmable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {self.color_mode}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._device = self.coordinator.data[self._device_id]
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if brightness_supported(self.supported_color_modes):
            await self._device.fade_to_brightness(
                brightness_to_value(
                    self.BRIGHTNESS_SCALE,
                    kwargs.get(ATTR_BRIGHTNESS, self._last_brightness),
                )
            )
        else:
            await self._device.switch_on()

        await asyncio.sleep(STATUS_UPDATE_DELAY)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if brightness_supported(self.supported_color_modes):
            self._last_brightness = self.brightness
            await self._device.fade_to_brightness(0)
        else:
            await self._device.switch_off()

        await asyncio.sleep(STATUS_UPDATE_DELAY)
        await self.coordinator.async_refresh()


class LunatoneLineBroadcastLight(
    CoordinatorEntity[LunatoneInfoDataUpdateCoordinator], LightEntity
):
    """Representation of a Lunatone line broadcast light."""

    BRIGHTNESS_SCALE = (1, 100)

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator_info: LunatoneInfoDataUpdateCoordinator,
        coordinator_devices: LunatoneDevicesDataUpdateCoordinator,
        broadcast: DALIBroadcast,
    ) -> None:
        """Initialize a Lunatone line broadcast light."""
        super().__init__(coordinator_info)
        self._coordinator_devices = coordinator_devices
        self._broadcast = broadcast

        line = broadcast.line

        self._attr_unique_id = f"{coordinator_info.data.device.serial}-line{line}"

        line_device = self.coordinator.data.lines[str(line)].device
        extra_info: dict = {}
        if line_device.serial != coordinator_info.data.device.serial:
            extra_info.update(
                serial_number=str(line_device.serial),
                hw_version=line_device.pcb,
                model_id=f"{line_device.article_number}{line_device.article_info}",
            )

        assert self.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=f"DALI Line {line}",
            via_device=(DOMAIN, str(coordinator_info.data.device.serial)),
            **extra_info,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        line_status = self.coordinator.data.lines[str(self._broadcast.line)].line_status
        return super().available and line_status == LineStatus.OK

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the line to turn on."""
        await self._broadcast.fade_to_brightness(
            brightness_to_value(self.BRIGHTNESS_SCALE, kwargs.get(ATTR_BRIGHTNESS, 255))
        )

        await asyncio.sleep(STATUS_UPDATE_DELAY)
        await self._coordinator_devices.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the line to turn off."""
        await self._broadcast.fade_to_brightness(0)

        await asyncio.sleep(STATUS_UPDATE_DELAY)
        await self._coordinator_devices.async_refresh()
