"""Platform for climate integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW, AtaDevice, AtwDevice
import pymelcloud.ata_device as ata
import pymelcloud.atw_device as atw
from pymelcloud.atw_device import (
    PROPERTY_ZONE_1_OPERATION_MODE,
    PROPERTY_ZONE_2_OPERATION_MODE,
    Zone,
)
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MelCloudDevice
from .const import (
    ATTR_STATUS,
    ATTR_VANE_HORIZONTAL,
    ATTR_VANE_HORIZONTAL_POSITIONS,
    ATTR_VANE_VERTICAL,
    ATTR_VANE_VERTICAL_POSITIONS,
    CONF_POSITION,
    DOMAIN,
    SERVICE_SET_VANE_HORIZONTAL,
    SERVICE_SET_VANE_VERTICAL,
)

SCAN_INTERVAL = timedelta(seconds=60)


ATA_HVAC_MODE_LOOKUP = {
    ata.OPERATION_MODE_HEAT: HVACMode.HEAT,
    ata.OPERATION_MODE_DRY: HVACMode.DRY,
    ata.OPERATION_MODE_COOL: HVACMode.COOL,
    ata.OPERATION_MODE_FAN_ONLY: HVACMode.FAN_ONLY,
    ata.OPERATION_MODE_HEAT_COOL: HVACMode.HEAT_COOL,
}
ATA_HVAC_MODE_REVERSE_LOOKUP = {v: k for k, v in ATA_HVAC_MODE_LOOKUP.items()}


ATW_ZONE_HVAC_MODE_LOOKUP = {
    atw.ZONE_OPERATION_MODE_HEAT: HVACMode.HEAT,
    atw.ZONE_OPERATION_MODE_COOL: HVACMode.COOL,
}
ATW_ZONE_HVAC_MODE_REVERSE_LOOKUP = {v: k for k, v in ATW_ZONE_HVAC_MODE_LOOKUP.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MelCloud device climate based on config_entry."""
    mel_devices = hass.data[DOMAIN][entry.entry_id]
    entities: list[AtaDeviceClimate | AtwDeviceZoneClimate] = [
        AtaDeviceClimate(mel_device, mel_device.device)
        for mel_device in mel_devices[DEVICE_TYPE_ATA]
    ]
    entities.extend(
        [
            AtwDeviceZoneClimate(mel_device, mel_device.device, zone)
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
            for zone in mel_device.device.zones
        ]
    )
    async_add_entities(
        entities,
        True,
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_VANE_HORIZONTAL,
        {vol.Required(CONF_POSITION): cv.string},
        "async_set_vane_horizontal",
    )
    platform.async_register_entity_service(
        SERVICE_SET_VANE_VERTICAL,
        {vol.Required(CONF_POSITION): cv.string},
        "async_set_vane_vertical",
    )


class MelCloudClimate(ClimateEntity):
    """Base climate device."""

    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, device: MelCloudDevice) -> None:
        """Initialize the climate."""
        self.api = device
        self._base_device = self.api.device

    async def async_update(self):
        """Update state from MELCloud."""
        await self.api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self.api.device_info

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._base_device.temperature_increment


class AtaDeviceClimate(MelCloudClimate):
    """Air-to-Air climate device."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.SWING_MODE
    )

    def __init__(self, device: MelCloudDevice, ata_device: AtaDevice) -> None:
        """Initialize the climate."""
        super().__init__(device)
        self._device = ata_device

        self._attr_name = device.name
        self._attr_unique_id = f"{self.api.device.serial}-{self.api.device.mac}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes with device specific additions."""
        attr = {}

        if vane_horizontal := self._device.vane_horizontal:
            attr.update(
                {
                    ATTR_VANE_HORIZONTAL: vane_horizontal,
                    ATTR_VANE_HORIZONTAL_POSITIONS: self._device.vane_horizontal_positions,
                }
            )

        if vane_vertical := self._device.vane_vertical:
            attr.update(
                {
                    ATTR_VANE_VERTICAL: vane_vertical,
                    ATTR_VANE_VERTICAL_POSITIONS: self._device.vane_vertical_positions,
                }
            )
        return attr

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        mode = self._device.operation_mode
        if not self._device.power or mode is None:
            return HVACMode.OFF
        return ATA_HVAC_MODE_LOOKUP.get(mode)

    def _apply_set_hvac_mode(
        self, hvac_mode: HVACMode, set_dict: dict[str, Any]
    ) -> None:
        """Apply hvac mode changes to a dict used to call _device.set."""
        if hvac_mode == HVACMode.OFF:
            set_dict["power"] = False
            return

        operation_mode = ATA_HVAC_MODE_REVERSE_LOOKUP.get(hvac_mode)
        if operation_mode is None:
            raise ValueError(f"Invalid hvac_mode [{hvac_mode}]")

        set_dict["operation_mode"] = operation_mode
        if self.hvac_mode == HVACMode.OFF:
            set_dict["power"] = True

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        set_dict: dict[str, Any] = {}
        self._apply_set_hvac_mode(hvac_mode, set_dict)
        await self._device.set(set_dict)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [HVACMode.OFF] + [
            ATA_HVAC_MODE_LOOKUP[mode]
            for mode in self._device.operation_modes
            if mode in ATA_HVAC_MODE_LOOKUP
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.room_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        set_dict: dict[str, Any] = {}
        if ATTR_HVAC_MODE in kwargs:
            self._apply_set_hvac_mode(
                kwargs.get(ATTR_HVAC_MODE, self.hvac_mode), set_dict
            )

        if ATTR_TEMPERATURE in kwargs:
            set_dict["target_temperature"] = kwargs.get(ATTR_TEMPERATURE)

        if set_dict:
            await self._device.set(set_dict)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._device.fan_speed

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._device.set({"fan_speed": fan_mode})

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self._device.fan_speeds

    async def async_set_vane_horizontal(self, position: str) -> None:
        """Set horizontal vane position."""
        if position not in self._device.vane_horizontal_positions:
            raise ValueError(
                f"Invalid horizontal vane position {position}. Valid positions: [{self._device.vane_horizontal_positions}]."
            )
        await self._device.set({ata.PROPERTY_VANE_HORIZONTAL: position})

    async def async_set_vane_vertical(self, position: str) -> None:
        """Set vertical vane position."""
        if position not in self._device.vane_vertical_positions:
            raise ValueError(
                f"Invalid vertical vane position {position}. Valid positions: [{self._device.vane_vertical_positions}]."
            )
        await self._device.set({ata.PROPERTY_VANE_VERTICAL: position})

    @property
    def swing_mode(self) -> str | None:
        """Return vertical vane position or mode."""
        return self._device.vane_vertical

    async def async_set_swing_mode(self, swing_mode) -> None:
        """Set vertical vane position or mode."""
        await self.async_set_vane_vertical(swing_mode)

    @property
    def swing_modes(self) -> list[str] | None:
        """Return a list of available vertical vane positions and modes."""
        return self._device.vane_vertical_positions

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._device.set({"power": True})

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._device.set({"power": False})

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        min_value = self._device.target_temperature_min
        if min_value is not None:
            return min_value

        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        max_value = self._device.target_temperature_max
        if max_value is not None:
            return max_value

        return DEFAULT_MAX_TEMP


class AtwDeviceZoneClimate(MelCloudClimate):
    """Air-to-Water zone climate device."""

    _attr_max_temp = 30
    _attr_min_temp = 10
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self, device: MelCloudDevice, atw_device: AtwDevice, atw_zone: Zone
    ) -> None:
        """Initialize the climate."""
        super().__init__(device)
        self._device = atw_device
        self._zone = atw_zone

        self._attr_name = f"{device.name} {self._zone.name}"
        self._attr_unique_id = f"{self.api.device.serial}-{atw_zone.zone_index}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes with device specific additions."""
        data = {
            ATTR_STATUS: ATW_ZONE_HVAC_MODE_LOOKUP.get(
                self._zone.status, self._zone.status
            )
        }
        return data

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        mode = self._zone.operation_mode
        if not self._device.power or mode is None:
            return HVACMode.OFF
        return ATW_ZONE_HVAC_MODE_LOOKUP.get(mode, HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._device.set({"power": False})
            return

        operation_mode = ATW_ZONE_HVAC_MODE_REVERSE_LOOKUP.get(hvac_mode)
        if operation_mode is None:
            raise ValueError(f"Invalid hvac_mode [{hvac_mode}]")

        if self._zone.zone_index == 1:
            props = {PROPERTY_ZONE_1_OPERATION_MODE: operation_mode}
        else:
            props = {PROPERTY_ZONE_2_OPERATION_MODE: operation_mode}
        if self.hvac_mode == HVACMode.OFF:
            props["power"] = True
        await self._device.set(props)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return [self.hvac_mode]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zone.room_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._zone.target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self._zone.set_target_temperature(
            kwargs.get("temperature", self.target_temperature)
        )
