"""Test Diagnostics utils."""

from datetime import datetime

from homeassistant.components.diagnostics import (
    REDACTED,
    async_redact_data,
    entity_entry_as_dict,
)
from homeassistant.helpers.entity_registry import RegistryEntry


def test_redact() -> None:
    """Test the async_redact_data helper."""
    data = {
        "key1": "value1",
        "key2": ["value2_a", "value2_b"],
        "key3": [["value_3a", "value_3b"], ["value_3c", "value_3d"]],
        "key4": {
            "key4_1": "value4_1",
            "key4_2": ["value4_2a", "value4_2b"],
            "key4_3": [["value4_3a", "value4_3b"], ["value4_3c", "value4_3d"]],
        },
        "key5": None,
        "key6": "",
        "key7": False,
    }

    to_redact = {
        "key1",
        "key3",
        "key4_1",
        "key5",
        "key6",
        "key7",
    }

    assert async_redact_data(data, to_redact) == {
        "key1": REDACTED,
        "key2": ["value2_a", "value2_b"],
        "key3": REDACTED,
        "key4": {
            "key4_1": REDACTED,
            "key4_2": ["value4_2a", "value4_2b"],
            "key4_3": [["value4_3a", "value4_3b"], ["value4_3c", "value4_3d"]],
        },
        "key5": None,
        "key6": "",
        "key7": REDACTED,
    }


def test_entity_entry_as_dict() -> None:
    """Test entity_entry_as_dict."""
    created = datetime.fromisoformat("2024-01-01T00:00:00+00:00")
    entry = RegistryEntry(
        entity_id="sensor.test_sensor",
        unique_id="unique123",
        platform="test",
        capabilities=None,
        config_entry_id=None,
        config_subentry_id=None,
        created_at=created,
        device_id=None,
        disabled_by=None,
        entity_category=None,
        has_entity_name=False,
        hidden_by=None,
        id=None,
        options=None,
        original_device_class=None,
        original_icon=None,
        original_name="Test Sensor",
        object_id_base=None,
        suggested_object_id=None,
        supported_features=0,
        translation_key=None,
        unit_of_measurement=None,
    )

    result = entity_entry_as_dict(entry)

    assert isinstance(result, dict)
    assert "_cache" not in result
    assert result["entity_id"] == "sensor.test_sensor"
    assert result["unique_id"] == "unique123"
    assert result["platform"] == "test"
    assert result["original_name"] == "Test Sensor"
    assert result["supported_features"] == 0
    assert result["created_at"] == created
