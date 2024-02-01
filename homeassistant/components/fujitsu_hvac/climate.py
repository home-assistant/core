"""Support for Fujitsu HVAC devices that use the Ayla Iot platform."""
from asyncio import timeout
from contextlib import suppress
from typing import Any

from ayla_iot_unofficial import AylaAuthError, new_ayla_api
from ayla_iot_unofficial.fujitsu_hvac import Capability, FujitsuHVAC

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    API_TIMEOUT,
    AYLA_APP_ID,
    AYLA_APP_SECRET,
    CONF_DEVICE,
    CONF_EUROPE,
    DOMAIN,
    FAN_MODE_MAP,
    HVAC_MODE_MAP,
    SWING_MODE_MAP,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one Fujitsu HVAC device."""
    api = new_ayla_api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        AYLA_APP_ID,
        AYLA_APP_SECRET,
        europe=entry.data[CONF_EUROPE],
    )

    try:
        async with timeout(API_TIMEOUT):
            await api.async_sign_in()
    except (TimeoutError, AylaAuthError):
        return

    devices = await api.async_get_devices()
    for dev in devices:
        if dev.device_serial_number == entry.data[CONF_DEVICE]:
            await dev.async_update()
            async_add_entities([FujitsuHVACDevice(dev)])
            return


class FujitsuHVACDevice(ClimateEntity):
    """Represent a Fujitsu HVAC device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.5
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, dev: FujitsuHVAC) -> None:
        """Set up static attributes."""
        self._dev = dev

        self._attr_unique_id = f"{DOMAIN}_{self._dev.device_serial_number}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._dev.device_serial_number)},
            name=self._dev.device_name,
            manufacturer="Fujitsu",
            model=self._dev.property_values["model_name"],
            serial_number=self._dev.device_serial_number,
            sw_version=self._dev.property_values["mcu_firmware_version"],
        )
        self.update_attributes()

    async def async_update(self) -> None:
        """Gather data from API and update our attributes."""
        try:
            if self._dev.ayla_api.token_expiring_soon:
                await self._dev.ayla_api.refresh_auth()
        except AylaAuthError:
            await self._dev.ayla_api.async_sign_in()

        await self._dev.async_update()
        self.update_attributes()

    def update_attributes(self) -> None:
        """Update all dynamic attributes."""
        self._attr_supported_features = self._get_supported_features()
        self._attr_current_temperature = self._dev.sensed_temp
        self._attr_fan_mode = self._get_fan_mode()
        self._attr_fan_modes = self._get_fan_modes()
        self._attr_hvac_mode = self._get_hvac_mode()
        self._attr_hvac_modes = self._get_hvac_modes()
        self._attr_swing_mode = self._get_swing_mode()
        self._attr_swing_modes = self._get_swing_modes()
        self._attr_target_temperature = self._get_target_temperature()
        (
            self._attr_min_temp,
            self._attr_max_temp,
        ) = self._dev.temperature_range

    def _get_fan_mode(self) -> str | None:
        with suppress(KeyError):
            return FAN_MODE_MAP.inverse[self._dev.fan_speed]

        return None

    def _get_fan_modes(self) -> list[str] | None:
        ret = [
            FAN_MODE_MAP.inverse[mode]
            for mode in self._dev.supported_fan_speeds
            if mode in FAN_MODE_MAP.inverse
        ]

        if len(ret) > 0:
            return ret

        return None

    def _get_hvac_mode(self) -> HVACMode | None:
        with suppress(KeyError):
            return HVAC_MODE_MAP.inverse[self._dev.op_mode]

        return None

    def _get_hvac_modes(self) -> list[HVACMode]:
        ret = [
            HVAC_MODE_MAP.inverse[mode]
            for mode in self._dev.supported_op_modes
            if mode in HVAC_MODE_MAP.inverse
        ]

        return ret

    def _get_swing_mode(self) -> str | None:
        with suppress(KeyError):
            return SWING_MODE_MAP.inverse[self._dev.swing_mode]

        return None

    def _get_swing_modes(self) -> list[str] | None:
        ret = [
            SWING_MODE_MAP.inverse[mode]
            for mode in self._dev.supported_swing_modes
            if mode in SWING_MODE_MAP.inverse
        ]

        if len(ret) > 0:
            return ret

        return None

    def _get_target_temperature(self) -> float | None:
        return float(self._dev.set_temp)

    def _get_supported_features(self) -> ClimateEntityFeature:
        ret = ClimateEntityFeature.TARGET_TEMPERATURE
        if self._dev.has_capability(Capability.OP_FAN):
            ret |= ClimateEntityFeature.FAN_MODE

        if self._dev.has_capability(
            Capability.SWING_HORIZONTAL
        ) or self._dev.has_capability(Capability.SWING_VERTICAL):
            ret |= ClimateEntityFeature.SWING_MODE

        return ret

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        with suppress(KeyError):
            await self._dev.async_set_op_mode(HVAC_MODE_MAP[hvac_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set Fan mode."""
        with suppress(KeyError):
            await self._dev.async_set_fan_speed(FAN_MODE_MAP[fan_mode])

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        with suppress(KeyError):
            await self._dev.async_set_swing_mode(SWING_MODE_MAP[swing_mode])

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._dev.async_set_set_temp(temperature)
