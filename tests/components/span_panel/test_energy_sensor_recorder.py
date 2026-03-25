"""Energy sensors exclude volatile attributes from recorder history (#197)."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.span_panel.sensor_base import SpanEnergySensorBase


def test_span_energy_sensor_combined_unrecorded_includes_high_churn_attributes() -> (
    None
):
    """Recorder must not persist grace-period / dip diagnostic attributes."""

    combined = SpanEnergySensorBase._Entity__combined_unrecorded_attributes
    for key in (
        "energy_offset",
        "grace_period_remaining",
        "last_dip_delta",
        "last_valid_changed",
        "last_valid_state",
        "tabs",
        "using_grace_period",
        "voltage",
    ):
        assert key in combined, f"missing unrecorded key: {key}"

    assert SensorEntity._entity_component_unrecorded_attributes <= combined, (
        "sensor component exclusions (e.g. options) must remain"
    )
