"""Test deprecated binary sensor device classes."""
from functools import partial

from homeassistant.components import binary_sensor

from .util import import_and_test_deprecated_costant

import_deprecated = partial(
    import_and_test_deprecated_costant,
    module=binary_sensor,
    constant_prefix="DEVICE_CLASS_",
)
