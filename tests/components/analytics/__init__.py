"""Tests for the analytics integration."""

MOCK_SNAPSHOT_PAYLOAD = {
    "hue": {
        "devices": [
            {
                "entry_type": None,
                "has_configuration_url": True,
                "hw_version": None,
                "manufacturer": "Signify Netherlands B.V.",
                "model": "Hue Bridge BSB002",
                "model_id": "BSB002",
                "sw_version": "1969118030",
                "via_device": None,
                "entities": [
                    {
                        "assumed_state": None,
                        "domain": "sensor",
                        "entity_category": "diagnostic",
                        "has_entity_name": True,
                        "original_device_class": None,
                        "unit_of_measurement": None,
                    },
                ],
            },
            {
                "entry_type": None,
                "has_configuration_url": False,
                "hw_version": None,
                "manufacturer": "Signify Netherlands B.V.",
                "model": "Hue color lamp",
                "model_id": "LCA001",
                "sw_version": "1.123.5",
                "via_device": ("hue", 0),
                "entities": [
                    {
                        "assumed_state": False,
                        "domain": "light",
                        "entity_category": None,
                        "has_entity_name": True,
                        "original_device_class": None,
                        "unit_of_measurement": None,
                    },
                ],
            },
        ],
        "entities": [],
    },
    "sun": {
        "devices": [],
        "entities": [
            {
                "assumed_state": None,
                "domain": "sensor",
                "entity_category": None,
                "has_entity_name": False,
                "original_device_class": "timestamp",
                "unit_of_measurement": None,
            },
        ],
    },
}

MOCK_SNAPSHOT_PAYLOAD_HASH = (
    "72297f6787d67667ede8ff1a9f58d9e11f810301def163ddf8d5142f63762905"
)
