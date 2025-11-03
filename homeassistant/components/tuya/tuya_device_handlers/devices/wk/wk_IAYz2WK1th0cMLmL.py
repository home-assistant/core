"""Quirks for Tuya."""

from __future__ import annotations

from ... import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ...const import TuyaDeviceCategory, TuyaDPCode
from ...conversion import scale_value_back_fixed_scale_1, scale_value_fixed_scale_1
from ...homeassistant import TuyaClimateHVACMode, TuyaEntityCategory

(
    # This model has invalid scale 0 for temperature dps - force scale 1
    TuyaDeviceQuirk()
    .applies_to(category=TuyaDeviceCategory.WK, product_id="IAYz2WK1th0cMLmL")
    .add_climate(
        key="wk",
        switch_only_hvac_mode=TuyaClimateHVACMode.HEAT_COOL,
        current_temperature_state_conversion=scale_value_fixed_scale_1,
        target_temperature_state_conversion=scale_value_fixed_scale_1,
        target_temperature_command_conversion=scale_value_back_fixed_scale_1,
    )
    .add_switch(
        key=TuyaDPCode.CHILD_LOCK,
        translation_key="child_lock",
        translation_string="Child lock",
        entity_category=TuyaEntityCategory.CONFIG,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
