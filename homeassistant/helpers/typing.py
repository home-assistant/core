"""Typing Helpers for Home-Assistant."""
from typing import Dict, Any, Tuple

import homeassistant.core

# pylint: disable=invalid-name

GPSType = Tuple[float, float]
ConfigType = Dict[str, Any]
HomeAssistantType = homeassistant.core.HomeAssistant

# Custom type for recorder Queries
QueryType = Any
