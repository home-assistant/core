"""Quirks for Tuya."""

from __future__ import annotations

from ..const import DPCode
from ..xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ..xternal_tuya_quirks.cover import CommonCoverType
from ..xternal_tuya_quirks.select import CommonSelectType
from ..xternal_tuya_quirks.sensor import CommonSensorType

(
    # This model has percent_state and percent_control but percent_state never
    # gets updated - force percent_control instead
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="g1cp07dsqnbdbbki")
    .add_common_cover(
        key=DPCode.CONTROL,
        common_type=CommonCoverType.CURTAIN,
        current_position_dp_code=DPCode.PERCENT_CONTROL,
        set_position_dp_code=DPCode.PERCENT_CONTROL,
    )
    .add_common_select(
        key=DPCode.CONTROL_BACK_MODE,
        common_type=CommonSelectType.CONTROL_BACK_MODE,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
(
    # This model has percent_control / percent_state / situation_set
    # but they never get updated - use control instead to get the state
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="lfkr93x0ukp5gaia")
    .add_common_cover(
        key=DPCode.CONTROL,
        common_type=CommonCoverType.CURTAIN,
        current_state_dp_code=DPCode.CONTROL,
    )
    .add_common_select(
        key=DPCode.CONTROL_BACK_MODE,
        common_type=CommonSelectType.CONTROL_BACK_MODE,
    )
    .add_common_sensor(
        key=DPCode.TIME_TOTAL,
        common_type=CommonSensorType.TIME_TOTAL,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
