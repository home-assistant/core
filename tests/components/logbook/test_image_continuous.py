"""Test that image entities are treated as continuous in logbook filtering.

This verifies the fix for https://github.com/home-assistant/core/issues/161039
where Roborock map image entities spammed Activity with frequent state changes
during cleaning. Image entities have timestamps as state values and should be
excluded from Activity, similar to counter and proximity domains.
"""

from homeassistant.components.logbook.const import ALWAYS_CONTINUOUS_DOMAINS
from homeassistant.components.logbook.helpers import (
    _is_state_filtered,
    async_filter_entities,
)
from homeassistant.core import HomeAssistant, State


def test_image_in_always_continuous_domains() -> None:
    """Test that image domain is in ALWAYS_CONTINUOUS_DOMAINS."""
    assert "image" in ALWAYS_CONTINUOUS_DOMAINS


def test_image_state_change_is_filtered() -> None:
    """Test that image entity state changes are filtered by logbook.

    Image entities use timestamps as state values. Frequent updates
    (e.g., Roborock map updates during cleaning) should not appear
    in the Activity log.
    """
    old_state = State("image.roborock_map", "2026-01-01T00:00:00+00:00")
    new_state = State("image.roborock_map", "2026-01-01T00:00:15+00:00")
    assert _is_state_filtered(new_state, old_state) is True


def test_image_entity_filtered_from_subscription(hass: HomeAssistant) -> None:
    """Test that image entities are filtered from logbook entity subscriptions."""
    entity_ids = [
        "light.kitchen",
        "image.roborock_map",
        "sensor.temperature",
    ]
    result = async_filter_entities(hass, entity_ids)
    assert "image.roborock_map" not in result
    assert "light.kitchen" in result
    assert "sensor.temperature" in result
