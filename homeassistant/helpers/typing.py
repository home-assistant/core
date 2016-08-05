"""Typing Helpers for Home-Assistant."""
from datetime import date, datetime
from typing import Dict, Any


# HACK: mypy/pytype will import, other interpreters will not; this is to avoid
#       circular dependencies where the type is needed.
# pylint: disable=using-constant-test,unused-import
if False:
    from homeassistant.core import HomeAssistant  # NOQA
# ENDHACK

# pylint: disable=invalid-name
ConfigType = Dict[str, Any]
Date = date
DateTime = datetime
HomeAssistantType = 'HomeAssistant'

# Custom type for recorder Queries
QueryType = Any
