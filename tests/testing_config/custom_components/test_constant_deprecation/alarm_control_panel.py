"""Test deprecated alarm control panel constants."""
from functools import partial

from .util import import_and_test_deprecated_costant

import_deprecated_code_format = partial(
    import_and_test_deprecated_costant,
    constant_prefix="FORMAT_",
)

import_deprecated_entity_feature = partial(
    import_and_test_deprecated_costant,
    constant_prefix="SUPPORT_ALARM_",
)
