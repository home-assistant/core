"""Typing Helpers for Home Assistant."""
from typing import Dict, Any, Tuple, Optional

import homeassistant.core

# pylint: disable=invalid-name

GPSType = Tuple[float, float]
ConfigType = Dict[str, Any]
EventType = homeassistant.core.Event
HomeAssistantType = homeassistant.core.HomeAssistant
ServiceDataType = Dict[str, Any]
TemplateVarsType = Optional[Dict[str, Any]]

# Custom type for recorder Queries
QueryType = Any
