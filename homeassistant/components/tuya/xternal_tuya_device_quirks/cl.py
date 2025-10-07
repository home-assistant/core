"""Quirks for Tuya."""

from __future__ import annotations

from ..xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY, TuyaDeviceQuirk
from ..xternal_tuya_quirks.cover import CommonCoverType
from ..xternal_tuya_quirks.select import CommonSelectType
from ..xternal_tuya_quirks.sensor import CommonSensorType

(
    # This model has percent_state and percent_control but percent_state never
    # gets updated - force percent_control instead
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="g1cp07dsqnbdbbki")
    .add_cover(
        key="control",
        cover_type=CommonCoverType.CURTAIN,
        current_position_dp_code="percent_control",
        current_state_dp_code="control",
        set_position_dp_code="percent_control",
        set_state_dp_code="control",
    )
    .add_select(
        key="control_back_mode",
        select_type=CommonSelectType.CONTROL_BACK_MODE,
        dp_code="control_back_mode",
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
(
    # This model has percent_control / percent_state / situation_set
    # but they never get updated - use control instead to get the state
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="lfkr93x0ukp5gaia")
    .add_cover(
        key="control",
        cover_type=CommonCoverType.CURTAIN,
        current_state_dp_code="control",
    )
    .add_select(
        key="control_back_mode",
        select_type=CommonSelectType.CONTROL_BACK_MODE,
        dp_code="control_back_mode",
    )
    .add_sensor(
        key="time_total",
        sensor_type=CommonSensorType.TIME_TOTAL,
        dp_code="time_total",
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
