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
    # This model has percent_state and percent_control but percent_state never
    # gets updated - force percent_control instead
    TuyaDeviceQuirk()
    .applies_to(category=TuyaDeviceCategory.CL, product_id="g1cp07dsqnbdbbki")
    .add_cover(
        key=TuyaDPCode.CONTROL,
        translation_key="curtain",
        translation_string="[%key:component::cover::entity_component::curtain::name%]",
        current_state_dp_code=TuyaDPCode.CONTROL,
        current_position_dp_code=TuyaDPCode.PERCENT_CONTROL,
        set_position_dp_code=TuyaDPCode.PERCENT_CONTROL,
        device_class=TuyaCoverDeviceClass.CURTAIN,
    )
    .add_select(
        key=TuyaDPCode.CONTROL_BACK_MODE,
        translation_key="curtain_motor_mode",
        translation_string="Motor mode",
        entity_category=TuyaEntityCategory.CONFIG,
        state_translations={"forward": "Forward", "back": "Back"},
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
