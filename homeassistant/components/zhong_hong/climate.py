"""Support for ZhongHong HVAC Controller."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZhongHongConfigEntry
from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    ZHONG_HONG_MODE_COOL,
    ZHONG_HONG_MODE_DRY,
    ZHONG_HONG_MODE_FAN_ONLY,
    ZHONG_HONG_MODE_HEAT,
)
from .coordinator import ZhongHongDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Mode mapping
MODE_TO_STATE = {
    ZHONG_HONG_MODE_COOL: HVACMode.COOL,
    ZHONG_HONG_MODE_HEAT: HVACMode.HEAT,
    ZHONG_HONG_MODE_DRY: HVACMode.DRY,
    ZHONG_HONG_MODE_FAN_ONLY: HVACMode.FAN_ONLY,
}

STATE_TO_MODE = {v: k for k, v in MODE_TO_STATE.items()}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZhongHongConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ZhongHong climate entities."""
    coordinator = entry.runtime_data

    entities = [
        ZhongHongClimate(coordinator, device_id, device)
        for device_id, device in coordinator.devices.items()
    ]

    async_add_entities(entities)


class ZhongHongClimate(
    CoordinatorEntity[ZhongHongDataUpdateCoordinator], ClimateEntity
):
    """Representation of a ZhongHong HVAC controller."""

    _attr_hvac_modes = [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0

    def __init__(
        self,
        coordinator: ZhongHongDataUpdateCoordinator,
        device_id: str,
        device,
    ) -> None:
        """Initialize the ZhongHong climate entity."""
        super().__init__(coordinator)

        self.device_id = device_id
        self._device = device
        addr_out, addr_in = device_id.split("_")

        self._attr_name = f"Zhong Hong HVAC {addr_out}_{addr_in}"
        self._attr_unique_id = f"zhong_hong_hvac_{device_id}"

        # Device info for grouping
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{device_id}")},
            "name": self._attr_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": "1.0",
            "via_device": (DOMAIN, f"{coordinator.host}_{coordinator.gateway_address}"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.hub_connected()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if not self.is_on:
            return HVACMode.OFF

        data = self.coordinator.data.get(self.device_id, {})
        operation = data.get("current_operation")
        if operation:
            return MODE_TO_STATE.get(operation.lower(), HVACMode.OFF)
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.data.get(self.device_id, {})
        return data.get("current_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        data = self.coordinator.data.get(self.device_id, {})
        return data.get("target_temperature")

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        data = self.coordinator.data.get(self.device_id, {})
        return data.get("is_on", False)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        data = self.coordinator.data.get(self.device_id, {})
        return data.get("current_fan_mode")

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return getattr(self._device, "fan_list", None)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return getattr(self._device, "min_temp", 16.0)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return getattr(self._device, "max_temp", 30.0)

    async def async_turn_on(self) -> None:
        """Turn on the AC."""
        success = await self.coordinator.async_send_command(self.device_id, "turn_on")
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        success = await self.coordinator.async_send_command(self.device_id, "turn_off")
        if success:
            await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        tasks = []

        if temperature is not None:
            tasks.append(
                self.coordinator.async_send_command(
                    self.device_id, "set_temperature", temperature
                )
            )

        if hvac_mode is not None:
            if hvac_mode == HVACMode.OFF:
                tasks.append(
                    self.coordinator.async_send_command(self.device_id, "turn_off")
                )
            else:
                # Turn on if not already on
                if not self.is_on:
                    tasks.append(
                        self.coordinator.async_send_command(self.device_id, "turn_on")
                    )
                mode_str = STATE_TO_MODE.get(hvac_mode, "").upper()
                if mode_str:
                    tasks.append(
                        self.coordinator.async_send_command(
                            self.device_id, "set_operation_mode", mode_str
                        )
                    )

        if tasks:
            # Wait for all commands to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            if any(isinstance(r, Exception) for r in results):
                _LOGGER.error("Some commands failed for %s", self.device_id)
            else:
                await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        success = True

        if not self.is_on:
            success = await self.coordinator.async_send_command(
                self.device_id, "turn_on"
            )

        if success:
            mode_str = STATE_TO_MODE.get(hvac_mode, "").upper()
            if mode_str:
                success = await self.coordinator.async_send_command(
                    self.device_id, "set_operation_mode", mode_str
                )

        if success:
            await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        success = await self.coordinator.async_send_command(
            self.device_id, "set_fan_mode", fan_mode
        )
        if success:
            await self.coordinator.async_request_refresh()
