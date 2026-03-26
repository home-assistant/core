"""Helper script to generate unit conversion JSON.

This will output "unit-factors.json" based on the currently available unit converters
to be copied to the frontend repository.

To update, run python3 -m script.unit_conversion
"""

from functools import reduce
from operator import ior
from pathlib import Path

from homeassistant.helpers.json import json_dumps
from homeassistant.util.unit_conversion import ALL_UNIT_CONVERTERS

Path("homeassistant/generated/unit-factors.json").write_text(
    json_dumps(reduce(ior, [conv.as_dict() for conv in ALL_UNIT_CONVERTERS], {})),
    encoding="utf8",
)
