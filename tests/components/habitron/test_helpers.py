"""Tests for the Habitron entity-area assignment helper."""

from unittest.mock import MagicMock, patch

from homeassistant.components.habitron._helpers import async_assign_entity_area


def test_assign_area_returns_when_entity_missing() -> None:
    """No registry write happens when the entity id cannot be resolved."""
    registry = MagicMock()
    registry.async_get_entity_id.return_value = None
    async_assign_entity_area(
        registry,
        domain="sensor",
        unique_id="x",
        area_index=1,
        area_member=0,
        area_ids={1: "area1"},
    )
    registry.async_update_entity.assert_not_called()


def test_assign_area_propagates_to_hidden_duplicates() -> None:
    """A hidden entity's area is also pushed to same-named duplicates."""
    registry = MagicMock()
    registry.async_get_entity_id.return_value = "sensor.x"
    entity = MagicMock()
    entity.hidden = True
    entity.device_id = "dev1"
    entity.original_name = "Light"
    registry.async_get.return_value = entity

    duplicate = MagicMock()
    duplicate.original_name = "Light"
    duplicate.entity_id = "sensor.dup"
    unrelated = MagicMock()
    unrelated.original_name = "Other"
    unrelated.entity_id = "sensor.other"

    with patch(
        "homeassistant.components.habitron._helpers.er.async_entries_for_device",
        return_value=[duplicate, unrelated],
    ):
        async_assign_entity_area(
            registry,
            domain="sensor",
            unique_id="x",
            area_index=2,
            area_member=0,
            area_ids={2: "area2"},
            propagate_to_hidden_duplicates=True,
        )

    updated = [call.args[0] for call in registry.async_update_entity.call_args_list]
    assert "sensor.x" in updated  # the primary entity
    assert "sensor.dup" in updated  # same original name → propagated
    assert "sensor.other" not in updated  # different name → left alone


def test_assign_area_skips_propagation_when_not_hidden() -> None:
    """A visible entity gets its own area but no duplicate propagation."""
    registry = MagicMock()
    registry.async_get_entity_id.return_value = "sensor.x"
    entity = MagicMock()
    entity.hidden = False  # visible → propagation short-circuits
    entity.device_id = "dev1"
    registry.async_get.return_value = entity

    with patch(
        "homeassistant.components.habitron._helpers.er.async_entries_for_device"
    ) as entries_for_device:
        async_assign_entity_area(
            registry,
            domain="sensor",
            unique_id="x",
            area_index=2,
            area_member=0,
            area_ids={2: "area2"},
            propagate_to_hidden_duplicates=True,
        )

    entries_for_device.assert_not_called()  # returned at the hidden check
    registry.async_update_entity.assert_called_once()  # only the primary entity
