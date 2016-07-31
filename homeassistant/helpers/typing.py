"""Typing Helpers for Home-Assistant."""

from typing import NewType, Dict, Any
import homeassistant.core

# pylint: disable=invalid-name

ConfigType = NewType('ConfigType', Dict[str, Any])
HomeAssistantType = homeassistant.core.HomeAssistant

# Custom type for recorder Queries
QueryType = NewType('QueryType', Any)
