"""Typing Helpers for Home-Assistant."""
from sys import version_info
from typing import Dict, Any

# NOTE: NewType added to typing in 3.5.2 in June, 2016; Since 3.5.2 includes
#       security fixes everyone on 3.5 should upgrade "soon"
NEWTYPE_TEST = version_info >= (3, 5, 2) or version_info[:2] == (3, 4)
if NEWTYPE_TEST:
    from typing import NewType


# HACK: mypy/pytype will import, other interpreters will not; this is to avoid
#       circular dependencies where the type is needed.
#       All homeassistant types should be imported this way.
#       Documentation
#       http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
# pylint: disable=using-constant-test,unused-import
if False:
    from homeassistant.core import HomeAssistant  # NOQA
    from homeassistant.helpers.unit_system import UnitSystem  # NOQA
# ENDHACK

# pylint: disable=invalid-name
if NEWTYPE_TEST:
    ConfigType = NewType('ConfigType', Dict[str, Any])
    HomeAssistantType = NewType('HomeAssistantType', 'HomeAssistant')
    UnitSystemType = NewType('UnitSystemType', 'UnitSystem')

    # Custom type for recorder Queries
    QueryType = NewType('QueryType', Any)

# Duplicates for 3.5.1
# pylint: disable=invalid-name
else:
    ConfigType = Dict[str, Any]  # type: ignore
    HomeAssistantType = 'HomeAssistant'  # type: ignore
    UnitSystemType = 'UnitSystemType'  # type: ignore

    # Custom type for recorder Queries
    QueryType = Any  # type: ignore
