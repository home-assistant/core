"""Unit tests for ``_sensor_value_fns`` helper functions.

Scoped to the wire-extractor helpers that the sensor + tracker platforms
share. The presence-predicates and value_fns are also exercised
indirectly through ``test_device_tracker.py``, ``test_lazy_sensors.py``,
and ``test_restore_gps.py``; this module pins direct unit-level
contracts those integration tests don't surface as crisply.
"""

from collections.abc import Mapping
from typing import Any

import pytest

from homeassistant.components.abetterrouteplanner._sensor_value_fns import (
    _extract_lat_long,
)


@pytest.mark.parametrize(
    ("lat", "lng"),
    [
        pytest.param(51, -1, id="both_int"),
        pytest.param(51, -1.5, id="lat_int_lng_float"),
        pytest.param(51.7, -1, id="lat_float_lng_int"),
    ],
)
def test_extract_lat_long_coerces_int_wire_to_float(lat: float, lng: float) -> None:
    """Int-typed lat/lng on the wire must be coerced to ``float``.

    The function's signature is ``tuple[float, float] | None`` but the
    ``isinstance`` guard admits both ``int`` and ``float``. The live
    extractor coerces to ``float`` so the live path is type-symmetric
    with the restore boundary (which already coerces via ``float(...)``
    in :func:`AbrpDeviceTracker.async_added_to_hass`).

    The parametrize exercises the ``int`` shape on EACH axis (both,
    lat-only, lng-only) so a lopsided fix (``float(lat)`` while leaving
    ``lng`` untouched) fails at least one row.
    """
    frame: Mapping[str, Any] = {"location": {"lat": lat, "long": lng}}
    result = _extract_lat_long(frame)
    assert result is not None
    # ``type(x) is float`` is stricter than ``isinstance(x, float)``:
    # an ``int`` leak would slip past ``isinstance`` only via subclass
    # promotion, which we explicitly don't want either way.
    assert type(result[0]) is float
    assert type(result[1]) is float
    assert result == (float(lat), float(lng))
