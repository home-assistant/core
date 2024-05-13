"""The tests for the Recorder component legacy models."""
from datetime import datetime, timedelta
from unittest.mock import PropertyMock

import pytest

from homeassistant.components.recorder.models.legacy import LegacyLazyState
from homeassistant.util import dt as dt_util


async def test_legacy_lazy_state_prefers_shared_attrs_over_attrs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState prefers shared_attrs over attributes."""
    row = PropertyMock(
        entity_id="sensor.invalid",
        shared_attrs='{"shared":true}',
        attributes='{"shared":false}',
    )
    assert LegacyLazyState(row, {}, None).attributes == {"shared": True}


async def test_legacy_lazy_state_handles_different_last_updated_and_last_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles different last_updated and last_changed."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        shared_attrs='{"shared":true}',
        last_updated_ts=now.timestamp(),
        last_changed_ts=(now - timedelta(seconds=60)).timestamp(),
    )
    lstate = LegacyLazyState(row, {}, None)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }


async def test_legacy_lazy_state_handles_same_last_updated_and_last_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles same last_updated and last_changed."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        shared_attrs='{"shared":true}',
        last_updated_ts=now.timestamp(),
        last_changed_ts=now.timestamp(),
    )
    lstate = LegacyLazyState(row, {}, None)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    lstate.last_updated = datetime(2020, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2020-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    lstate.last_changed = datetime(2020, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2020-06-12T03:04:01.000323+00:00",
        "last_updated": "2020-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
