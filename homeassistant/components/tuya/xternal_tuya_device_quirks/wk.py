"""Quirks for Tuya."""

from __future__ import annotations

from typing import cast

from ..const import DPCode
from ..models import IntegerTypeData
from ..xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ..xternal_tuya_quirks.climate import CommonClimateType
from ..xternal_tuya_quirks.sensor import CommonSensorType
from ..xternal_tuya_quirks.switch import CommonSwitchType
from ..xternal_tuya_quirks.utils import scale_value_force_scale_1

(
    # This model has percent_state and percent_control but percent_state never
    # gets updated - force percent_control instead
    TuyaDeviceQuirk()
    .applies_to(category="wk", product_id="IAYz2WK1th0cMLmL")
    .add_common_climate(
        key="wk",  # to avoid breaking change
        common_type=CommonClimateType.SWITCH_ONLY_HEAT_COOL,
        switch_dp_code=DPCode.SWITCH,
        current_temperature_dp_code=DPCode.UPPER_TEMP,
        set_temperature_dp_code=DPCode.TEMP_SET,
    )
    .add_common_sensor(
        key=DPCode.UPPER_TEMP,
        common_type=CommonSensorType.TEMPERATURE,
        state_conversion=lambda _device, dptype, value: scale_value_force_scale_1(
            cast(IntegerTypeData, dptype), cast(float, value)
        ),
    )
    .add_common_switch(
        key=DPCode.CHILD_LOCK,
        common_type=CommonSwitchType.CHILD_LOCK,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
