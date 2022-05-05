"""Test Diagnostics utils."""
from homeassistant.components.diagnostics import REDACTED, async_redact_data


def test_redact():
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
