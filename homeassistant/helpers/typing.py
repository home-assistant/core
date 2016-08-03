"""Typing Helpers for Home-Assistant."""
from typing import Dict, Any

import homeassistant.core

# pylint: disable=invalid-name

ConfigType = Dict[str, Any]
HomeAssistantType = homeassistant.core.HomeAssistant

# Custom type for recorder Queries
QueryType = Any
