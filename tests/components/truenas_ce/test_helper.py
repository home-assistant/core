"""Unit tests for ``homeassistant.components.truenas_ce.helper``.

Pure-function tests -- ``format_attribute``/``scaled_data_unit`` have no Home
Assistant dependency, so no ``hass`` fixture is needed.
"""

from __future__ import annotations

import pytest

from homeassistant.components.truenas_ce.helper import format_attribute


@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        ("zfs_arc_hits", "ZFS arc hits"),
        ("arc_zfs_hits", "Arc ZFS hits"),
        ("cpu_temp", "CPU temp"),
    ],
)
def test_format_attribute_zfs_uppercased(attr: str, expected: str) -> None:
    """ZFS is uppercased regardless of whether it leads the attribute name."""
    assert format_attribute(attr) == expected
