"""Quirks for Tuya."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tuya_sharing import CustomerDevice

from ..const import DPCode
from ..models import EnumTypeData, IntegerTypeData
from ..xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ..xternal_tuya_quirks.homeassistant import TuyaClimateHVACMode, TuyaEntityCategory
from ..xternal_tuya_quirks.utils import scale_value, scale_value_back


def _scale_value_force_scale_1(
    _device: CustomerDevice, dptype: EnumTypeData | IntegerTypeData | None, value: Any
) -> float:
    """Scale value to scale 1."""
    if TYPE_CHECKING:
        assert isinstance(dptype, IntegerTypeData)
        assert isinstance(value, int)
    return scale_value(value, dptype.step, 1)


def _scale_value_back_force_scale_1(
    _device: CustomerDevice, dptype: EnumTypeData | IntegerTypeData | None, value: Any
) -> int:
    """Unscale value to scale 1."""
    if TYPE_CHECKING:
        assert isinstance(dptype, IntegerTypeData)
        assert isinstance(value, float)
    return scale_value_back(value, dptype.step, 1)


(
    # This model has invalid scale 0 for temperature dps - force scale 1
    TuyaDeviceQuirk()
    .applies_to(category="wk", product_id="IAYz2WK1th0cMLmL")
    .add_climate(
        key="wk",
        switch_only_hvac_mode=TuyaClimateHVACMode.HEAT_COOL,
        current_temperature_state_conversion=_scale_value_force_scale_1,
        target_temperature_state_conversion=_scale_value_force_scale_1,
        target_temperature_command_conversion=_scale_value_back_force_scale_1,
    )
    .add_switch(
        key=DPCode.CHILD_LOCK,
        translation_key="child_lock",
        translation_string="Child lock",
        entity_category=TuyaEntityCategory.CONFIG,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
