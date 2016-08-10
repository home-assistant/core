"""Typing Helpers for Home-Assistant."""
from typing import Dict, Any

# NOTE: NewType added to typing in 3.5.2 in June, 2016; Since 3.5.2 includes
#       security fixes everyone on 3.5 should upgrade "soon"
try:
    from typing import NewType
except ImportError:
    NewType = None

# pylint: disable=invalid-name
if NewType:
    ConfigType = NewType('ConfigType', Dict[str, Any])

    # Custom type for recorder Queries
    QueryType = NewType('QueryType', Any)

# Duplicates for 3.5.1
# pylint: disable=invalid-name
else:
    ConfigType = Dict[str, Any]  # type: ignore

    # Custom type for recorder Queries
    QueryType = Any  # type: ignore
