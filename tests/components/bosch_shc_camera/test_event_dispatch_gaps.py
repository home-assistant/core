"""Tests closing coverage gaps in event_dispatch.py's alert-id bookkeeping.

Exercised through `build_data_and_dispatch` (the function the coordinator's
real polling tick actually calls), matching `test_event_dispatch.py`'s
existing style — see that file's module docstring for why the private
`_dispatch_new_event`/`_prune_alert_sent_ids` helpers are not called directly.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.event_dispatch import (
    build_data_and_dispatch,
)

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"
NOW = 1000.0


def _make_coord(**overrides: object) -> SimpleNamespace:
    coord = SimpleNamespace(
        cached_status=overrides.pop("cached_status", {}),
        cached_events=overrides.pop("cached_events", {}),
        last_event_ids=overrides.pop("last_event_ids", {}),
        alert_sent_ids=overrides.pop("alert_sent_ids", {}),
        camera_entities=overrides.pop("camera_entities", {}),
        hass=MagicMock(),
        spawn_tracked=MagicMock(),
    )
    for key, value in overrides.items():
        setattr(coord, key, value)
    return coord


def _cam_by_id(cam_id: str = CAM_ID, title: str = "Front Door") -> dict:
    return {cam_id: {"id": cam_id, "title": title}}


@pytest.mark.asyncio
async def test_unchanged_newest_event_id_resyncs_without_dispatch() -> None:
    """`newest_id == prev_id` (no new event since last tick) just keeps ids in sync.

    Covers the `elif newest_id:` tail branch in `build_data_and_dispatch` —
    distinct from the `newest_id != prev_id` branch that actually dispatches.
    """
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev1", "eventType": "MOVEMENT"}]},
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.hass.bus.async_fire.assert_not_called()
    coord.spawn_tracked.assert_not_called()
    assert coord.last_event_ids[CAM_ID] == "ev1"


@pytest.mark.asyncio
async def test_alert_sent_ids_pruned_once_past_64_entries() -> None:
    """`alert_sent_ids` sheds entries older than 120s once it grows past 64.

    Pre-seeds 64 stale entries (older than the 120s cutoff); dispatching a new
    event pushes the map to 65 — past the prune threshold — so every stale
    entry must be dropped, leaving only the just-dispatched id behind.
    """
    stale_cutoff = NOW - 121.0
    alert_sent_ids = {f"stale-{i}": stale_cutoff for i in range(64)}
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev-new", "eventType": "MOVEMENT"}]},
        last_event_ids={CAM_ID: "ev-old"},
        alert_sent_ids=alert_sent_ids,
    )

    with patch(
        "homeassistant.components.bosch_shc_camera.event_dispatch.time.monotonic",
        return_value=NOW,
    ):
        await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    assert coord.alert_sent_ids == {"ev-new": NOW}
