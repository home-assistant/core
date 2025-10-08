"""Quirks for Tuya."""

from __future__ import annotations

from ..const import DPCode
from ..xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ..xternal_tuya_quirks.homeassistant import TuyaCoverDeviceClass, TuyaEntityCategory

(
    # This model has percent_state and percent_control but percent_state never
    # gets updated - force percent_control instead
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="g1cp07dsqnbdbbki")
    .add_cover(
        key=DPCode.CONTROL,
        translation_key="curtain",
        translation_string="[%key:component::cover::entity_component::curtain::name%]",
        current_state_dp_code=DPCode.CONTROL,
        current_position_dp_code=DPCode.PERCENT_CONTROL,
        set_position_dp_code=DPCode.PERCENT_CONTROL,
        device_class=TuyaCoverDeviceClass.CURTAIN,
    )
    .add_select(
        key=DPCode.CONTROL_BACK_MODE,
        translation_key="curtain_motor_mode",
        translation_string="Motor mode",
        entity_category=TuyaEntityCategory.CONFIG,
        state_translations={"forward": "Forward", "back": "Back"},
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
(
    # This model has percent_control / percent_state / situation_set
    # but they never get updated - use control instead to get the state
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="lfkr93x0ukp5gaia")
    .add_cover(
        key=DPCode.CONTROL,
        translation_key="curtain",
        translation_string="[%key:component::cover::entity_component::curtain::name%]",
        current_state_dp_code=DPCode.CONTROL,
        device_class=TuyaCoverDeviceClass.CURTAIN,
    )
    .add_select(
        key=DPCode.CONTROL_BACK_MODE,
        translation_key="curtain_motor_mode",
        translation_string="Motor mode",
        entity_category=TuyaEntityCategory.CONFIG,
        state_translations={"forward": "Forward", "back": "Back"},
    )
    .add_sensor(
        key=DPCode.TIME_TOTAL,
        translation_key="last_operation_duration",
        translation_string="Last operation duration",
        entity_category=TuyaEntityCategory.DIAGNOSTIC,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
