"""Typing Helpers for Home-Assistant."""
# pylint: disable=invalid-name
try:
    from typing import NewType, Dict, Any
except ImportError:
    from typing import Dict, Any

    def NewType(name: str, typ: Any) -> Any:
        """Fake NewType, required for Python 3.5.1."""
        return typ

import homeassistant.core

ConfigType = NewType('ConfigType', Dict[str, Any])
HomeAssistantType = homeassistant.core.HomeAssistant

# Custom type for recorder Queries
QueryType = NewType('QueryType', Any)
