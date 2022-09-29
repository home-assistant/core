"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from enum import IntEnum
from functools import partial
from typing import Any, cast

from aiolifx.aiolifx import Light, MultiZoneDirection, MultiZoneEffectType
from aiolifx.connection import LIFXConnection

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    ATTR_REMAINING,
    DOMAIN,
    IDENTIFY_WAVEFORM,
    MESSAGE_RETRIES,
    MESSAGE_TIMEOUT,
    TARGET_ANY,
    UNAVAILABLE_GRACE,
)
from .util import (
    async_execute_lifx,
    get_real_mac_addr,
    infrared_brightness_option_to_value,
    infrared_brightness_value_to_option,
    lifx_features,
)

REQUEST_REFRESH_DELAY = 0.35
LIFX_IDENTIFY_DELAY = 3.0


class FirmwareEffect(IntEnum):
    """Enumeration of LIFX firmware effects."""

    OFF = 0
    MOVE = 1
    MORPH = 2
    FLAME = 3


class LIFXUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific lifx device."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: LIFXConnection,
        title: str,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        assert connection.device is not None
        self.connection = connection
        self.device: Light = connection.device
        self.lock = asyncio.Lock()
        self.active_effect = FirmwareEffect.OFF
        update_interval = timedelta(seconds=10)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{title} ({self.device.ip_addr})",
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    @callback
    def async_setup(self) -> None:
        """Change timeouts."""
        self.device.timeout = MESSAGE_TIMEOUT
        self.device.retry_count = MESSAGE_RETRIES
        self.device.unregister_timeout = UNAVAILABLE_GRACE

    @property
    def serial_number(self) -> str:
        """Return the internal mac address."""
        return cast(
            str, self.device.mac_addr
        )  # device.mac_addr is not the mac_address, its the serial number

    @property
    def mac_address(self) -> str:
        """Return the physical mac address."""
        return get_real_mac_addr(
            # device.mac_addr is not the mac_address, its the serial number
            self.device.mac_addr,
            self.device.host_firmware_version,
        )

    @property
    def label(self) -> str:
        """Return the label of the bulb."""
        return cast(str, self.device.label)

    @property
    def current_infrared_brightness(self) -> str | None:
        """Return the current infrared brightness as a string."""
        return infrared_brightness_value_to_option(self.device.infrared_brightness)

    def async_get_entity_id(self, platform: Platform, key: str) -> str | None:
        """Return the entity_id from the platform and key provided."""
        ent_reg = er.async_get(self.hass)
        return ent_reg.async_get_entity_id(
            platform, DOMAIN, f"{self.serial_number}_{key}"
        )

    async def async_identify_bulb(self) -> None:
        """Identify the device by flashing it three times."""
        bulb: Light = self.device
        if bulb.power_level:
            # just flash the bulb for three seconds
            await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
            return
        # Turn the bulb on first, flash for 3 seconds, then turn off
        await self.async_set_power(state=True, duration=1)
        await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
        await asyncio.sleep(LIFX_IDENTIFY_DELAY)
        await self.async_set_power(state=False, duration=1)

    async def _async_update_data(self) -> None:
        """Fetch all device data from the api."""
        async with self.lock:
            if self.device.host_firmware_version is None:
                self.device.get_hostfirmware()
            if self.device.product is None:
                self.device.get_version()

            response = await async_execute_lifx(self.device.get_color)

            if self.device.product is None:
                raise UpdateFailed(
                    f"Failed to fetch get version from device: {self.device.ip_addr}"
                )

            # device.mac_addr is not the mac_address, its the serial number
            if self.device.mac_addr == TARGET_ANY:
                self.device.mac_addr = response.target_addr

            # Update model-specific configuration
            if lifx_features(self.device)["multizone"]:
                await self.async_update_color_zones()
                await self.async_update_multizone_effect()

            if lifx_features(self.device)["hev"]:
                await self.async_get_hev_cycle()

            if lifx_features(self.device)["infrared"]:
                response = await async_execute_lifx(self.device.get_infrared)

    async def async_update_color_zones(self) -> None:
        """Get updated color information for each zone."""
        zone = 0
        top = 1
        while zone < top:
            # Each get_color_zones can update 8 zones at once
            resp = await async_execute_lifx(
                partial(self.device.get_color_zones, start_index=zone)
            )
            zone += 8
            top = resp.count

            # We only await multizone responses so don't ask for just one
            if zone == top - 1:
                zone -= 1

    def async_get_hev_cycle_state(self) -> bool | None:
        """Return the current HEV cycle state."""
        if self.device.hev_cycle is None:
            return None
        return bool(self.device.hev_cycle.get(ATTR_REMAINING, 0) > 0)

    async def async_get_hev_cycle(self) -> None:
        """Update the HEV cycle status from a LIFX Clean bulb."""
        if lifx_features(self.device)["hev"]:
            await async_execute_lifx(self.device.get_hev_cycle)

    async def async_set_waveform_optional(
        self, value: dict[str, Any], rapid: bool = False
    ) -> None:
        """Send a set_waveform_optional message to the device."""
        await async_execute_lifx(
            partial(self.device.set_waveform_optional, value=value, rapid=rapid)
        )

    async def async_get_color(self) -> None:
        """Send a get color message to the device."""
        await async_execute_lifx(self.device.get_color)

    async def async_set_power(self, state: bool, duration: int | None) -> None:
        """Send a set power message to the device."""
        await async_execute_lifx(
            partial(self.device.set_power, state, duration=duration)
        )

    async def async_set_color(
        self, hsbk: list[float | int | None], duration: int | None
    ) -> None:
        """Send a set color message to the device."""
        await async_execute_lifx(
            partial(self.device.set_color, hsbk, duration=duration)
        )

    async def async_set_color_zones(
        self,
        start_index: int,
        end_index: int,
        hsbk: list[float | int | None],
        duration: int | None,
        apply: int,
    ) -> None:
        """Send a set color zones message to the device."""
        await async_execute_lifx(
            partial(
                self.device.set_color_zones,
                start_index=start_index,
                end_index=end_index,
                color=hsbk,
                duration=duration,
                apply=apply,
            )
        )

    async def async_update_multizone_effect(self) -> None:
        """Update the device firmware effect running state."""
        await async_execute_lifx(self.device.get_multizone_effect)
        self.active_effect = FirmwareEffect[self.device.effect.get("effect", "OFF")]

    async def async_set_multizone_effect(
        self, effect: str, speed: float, direction: str, power_on: bool = True
    ) -> None:
        """Control the firmware-based Move effect on a multizone device."""
        if lifx_features(self.device)["multizone"] is True:
            if power_on and self.device.power_level == 0:
                await self.async_set_power(True, 0)

            await async_execute_lifx(
                partial(
                    self.device.set_multizone_effect,
                    effect=MultiZoneEffectType[effect.upper()].value,
                    speed=speed,
                    direction=MultiZoneDirection[direction.upper()].value,
                )
            )
            self.active_effect = FirmwareEffect[effect.upper()]

    def async_get_active_effect(self) -> int:
        """Return the enum value of the currently active firmware effect."""
        return self.active_effect.value

    async def async_set_hev_cycle_state(self, enable: bool, duration: int = 0) -> None:
        """Start or stop an HEV cycle on a LIFX Clean bulb."""
        if lifx_features(self.device)["hev"]:
            await async_execute_lifx(
                partial(self.device.set_hev_cycle, enable=enable, duration=duration)
            )

    async def async_set_infrared_brightness(self, option: str) -> None:
        """Set infrared brightness."""
        infrared_brightness = infrared_brightness_option_to_value(option)
        await async_execute_lifx(partial(self.device.set_infrared, infrared_brightness))
