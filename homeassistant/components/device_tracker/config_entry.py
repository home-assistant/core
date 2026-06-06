"""Code to set up a device tracker platform using a config entry."""

from functools import partial

from homeassistant.helpers.deprecation import (
    DeprecatedAlias,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

from . import (
    BaseTrackerEntity as _BaseTrackerEntity,
    ScannerEntity as _ScannerEntity,
    SourceType as _SourceType,
    TrackerEntity as _TrackerEntity,
    TrackerEntityDescription as _TrackerEntityDescription,
)

_DEPRECATED_TrackerEntity = DeprecatedAlias(
    _TrackerEntity, "homeassistant.components.device_tracker.TrackerEntity", "2027.6"
)
_DEPRECATED_ScannerEntity = DeprecatedAlias(
    _ScannerEntity, "homeassistant.components.device_tracker.ScannerEntity", "2027.6"
)
_DEPRECATED_BaseTrackerEntity = DeprecatedAlias(
    _BaseTrackerEntity,
    "homeassistant.components.device_tracker.BaseTrackerEntity",
    "2027.6",
)
_DEPRECATED_TrackerEntityDescription = DeprecatedAlias(
    _TrackerEntityDescription,
    "homeassistant.components.device_tracker.TrackerEntityDescription",
    "2027.6",
)
_DEPRECATED_SourceType = DeprecatedAlias(
    _SourceType, "homeassistant.components.device_tracker.SourceType", "2027.6"
)

# These can be removed if no deprecated aliases are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
