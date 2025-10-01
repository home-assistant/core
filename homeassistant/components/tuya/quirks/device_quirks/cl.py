"""Quirks for Tuya."""

from __future__ import annotations

from .. import TUYA_QUIRKS_REGISTRY
from ..device_quirk import TuyaCoverDeviceClass, TuyaDeviceQuirk

(
    # This model has percent_state and percent_control but percent_state never
    # gets updated - force percent_control instead
    TuyaDeviceQuirk()
    .applies_to(category="cl", product_id="g1cp07dsqnbdbbki")
    .add_cover(
        key="control",
        translation_key="curtain",
        translation_string="curtain",
        current_state_dp_code="control",
        current_position_dp_code="percent_control",
        set_position_dp_code="percent_control",
        device_class=TuyaCoverDeviceClass.CURTAIN,
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
        translation_key="curtain",
        translation_string="curtain",
        current_state_dp_code="control",
        device_class=TuyaCoverDeviceClass.CURTAIN,
    )
    .register(TUYA_QUIRKS_REGISTRY)
)
