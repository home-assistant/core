"""The Luxtronik models."""
# region Imports
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.water_heater import (
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.helpers.entity import EntityDescription

from .const import (
    DeviceKey,
    FirmwareVersionMinor,
    LuxCalculation,
    LuxOperationMode,
    LuxParameter,
    LuxVisibility,
)

# endregion Imports


@dataclass
class LuxtronikEntityDescription(EntityDescription):
    """Class describing Luxtronik entities."""

    icon_by_state: dict[str, str] | None = None
    has_entity_name = True

    device_key: DeviceKey = DeviceKey.heatpump
    luxtronik_key: LuxParameter | LuxCalculation = LuxParameter.UNSET
    translation_key_name: str | None = None
    visibility: LuxVisibility = LuxVisibility.UNSET
    invisibly_if_value = None
    min_firmware_version_minor: FirmwareVersionMinor | None = None


@dataclass
class LuxtronikWaterHeaterDescription(
    LuxtronikEntityDescription,
    WaterHeaterEntityEntityDescription,
):
    """Class describing Luxtronik water heater entities."""

    operation_list: list[str] = []
    supported_features: WaterHeaterEntityFeature = WaterHeaterEntityFeature(0)
    luxtronik_key_current_temperature: LuxCalculation = LuxCalculation.UNSET
    luxtronik_key_current_action: LuxCalculation = LuxCalculation.UNSET
    luxtronik_action_heating: LuxOperationMode | None = None
    luxtronik_key_target_temperature: LuxParameter = LuxParameter.UNSET
    luxtronik_key_target_temperature_high: LuxParameter = LuxParameter.UNSET
    luxtronik_key_target_temperature_low: LuxParameter = LuxParameter.UNSET
