"""Quirks for Tuya."""

from __future__ import annotations

from ... import TUYA_QUIRKS_REGISTRY
from ...builder import TuyaDeviceQuirk
from ...helpers import (
    TuyaCoverDeviceClass,
    TuyaDeviceCategory,
    TuyaDPCode,
    TuyaEntityCategory,
)

(
    # This model has percent_control / percent_state / situation_set
    # but they never get updated - use control instead to get the state
    TuyaDeviceQuirk()
    .applies_to(category=TuyaDeviceCategory.CL, product_id="lfkr93x0ukp5gaia")
    .add_cover(
        key=TuyaDPCode.CONTROL,
        translation_key="curtain",
        translation_string="[%key:component::cover::entity_component::curtain::name%]",
        current_state_dp_code=TuyaDPCode.CONTROL,
        device_class=TuyaCoverDeviceClass.CURTAIN,
    )
    .add_select(
        key=TuyaDPCode.CONTROL_BACK_MODE,
        translation_key="curtain_motor_mode",
        translation_string="Motor mode",
        entity_category=TuyaEntityCategory.CONFIG,
        state_translations={"forward": "Forward", "back": "Back"},
    )
    .add_sensor(
        key=TuyaDPCode.TIME_TOTAL,
        translation_key="last_operation_duration",
        translation_string="Last operation duration",
        entity_category=TuyaEntityCategory.DIAGNOSTIC,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
