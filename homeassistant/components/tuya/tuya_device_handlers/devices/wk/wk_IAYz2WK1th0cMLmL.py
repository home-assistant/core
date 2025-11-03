"""Quirks for Tuya."""

from __future__ import annotations

from ... import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ...const import TuyaDeviceCategory, TuyaDPCode
from ...homeassistant import TuyaClimateHVACMode, TuyaEntityCategory

(
    TuyaDeviceQuirk()
    .applies_to(category=TuyaDeviceCategory.WK, product_id="IAYz2WK1th0cMLmL")
    .add_climate(
        key="wk",
        switch_only_hvac_mode=TuyaClimateHVACMode.HEAT_COOL,
        current_temperature_dp_code=TuyaDPCode.UPPER_TEMP,
        # UPPER_TEMP uses incorrect scale 1 / step 5 - convert to proper temperature
        current_temperature_state_conversion=lambda _device, _def, value: value / 2,
        # TEMP_SET uses incorrect scale 0 / step 5 - convert to proper temperature
        target_temperature_dp_code=TuyaDPCode.TEMP_SET,
        target_temperature_state_conversion=lambda _device, _def, value: value / 2,
        target_temperature_command_conversion=lambda _device, _def, value: value * 2,
    )
    .add_switch(
        key=TuyaDPCode.CHILD_LOCK,
        translation_key="child_lock",
        translation_string="Child lock",
        entity_category=TuyaEntityCategory.CONFIG,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
