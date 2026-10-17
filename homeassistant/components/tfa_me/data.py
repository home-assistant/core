"""TFA.me station integration: data.py."""

from dataclasses import dataclass
from typing import Any


@dataclass
class TFAmeCoordinatorData:
    """Typed coordinator payload."""

    entities: dict[
        str, dict[str, Any]
    ]  # dict with unique IDs & measurement data, units, timestamp and more
    gateway_id: str  # 9 digit gateway/station serial hex number
    gateway_sw: str  # SW numbers (gateway/station & display unit)
