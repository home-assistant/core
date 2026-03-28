"""Helper script to generate unit conversion JSON.

This will output "unit-factors.json" based on the currently available unit converters
to be copied to the frontend repository.

To update, run python3 -m script.unit_conversion
"""

from pathlib import Path

from homeassistant.helpers.json import json_dumps_sorted
from homeassistant.util.unit_conversion import ALL_UNIT_CONVERTERS

_COMBINED_UNIT_FACTORS = {}
for conv in ALL_UNIT_CONVERTERS:
    conv_data = conv.as_dict()
    for unit_class, data in conv_data.items():
        if unit_class in _COMBINED_UNIT_FACTORS:
            raise ValueError(
                f"Duplicate UNIT_CLASS '{unit_class}' encountered while "
                "building unit conversion JSON"
            )
        _COMBINED_UNIT_FACTORS[unit_class] = data

Path("homeassistant/generated/unit-factors.json").write_text(
    json_dumps_sorted(_COMBINED_UNIT_FACTORS),
    encoding="utf8",
)
