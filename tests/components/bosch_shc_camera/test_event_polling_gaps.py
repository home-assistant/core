"""Tests for event_polling.py's parallel per-camera events-fetch pass."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera.event_polling import (
    _fetch_one_camera_events,
    poll_events,
)

CAM_ID = "cam-1"
HEADERS = {"Authorization": "Bearer tok"}


def _make_coordinator(**overrides: object) -> SimpleNamespace:
    defaults = {
        "last_event_ids": {},
        "cached_events": {},
        "err_str": staticmethod(lambda err: str(err) or repr(err)),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _resp_cm(status: int, json_body: object = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_body)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestFetchOneCameraEvents:
    """`_fetch_one_camera_events`'s last_event/full-fetch branching."""

    @pytest.mark.asyncio
    async def test_last_event_unchanged_skips_full_fetch(self) -> None:
        """A matching cached last_event id returns the cached snapshot, no full fetch."""
        coordinator = _make_coordinator(
            last_event_ids={CAM_ID: "evt-1"},
            cached_events={CAM_ID: [{"id": "evt-1"}]},
        )
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(200, {"id": "evt-1"}))

        cam_id, events, ok, skip_full_fetch = await _fetch_one_camera_events(
            coordinator, CAM_ID, session, HEADERS
        )

        assert cam_id == CAM_ID
        assert events == [{"id": "evt-1"}]
        assert ok is True
        assert skip_full_fetch is True
        session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_last_event_changed_triggers_full_fetch(self) -> None:
        """A different (or new) last_event id falls through to the full events list."""
        coordinator = _make_coordinator(last_event_ids={CAM_ID: "evt-old"})
        le_resp = _resp_cm(200, {"id": "evt-new"})
        full_resp = _resp_cm(200, [{"id": "evt-new"}, {"id": "evt-old"}])
        session = MagicMock()
        session.get = MagicMock(side_effect=[le_resp, full_resp])

        _, events, ok, skip_full_fetch = await _fetch_one_camera_events(
            coordinator, CAM_ID, session, HEADERS
        )

        assert events == [{"id": "evt-new"}, {"id": "evt-old"}]
        assert ok is True
        assert skip_full_fetch is False
        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_last_event_non_200_falls_through_to_full_fetch(self) -> None:
        """A non-200 last_event response is treated like "unknown", not an error."""
        coordinator = _make_coordinator()
        le_resp = _resp_cm(500)
        full_resp = _resp_cm(200, [{"id": "evt-1"}])
        session = MagicMock()
        session.get = MagicMock(side_effect=[le_resp, full_resp])

        _, events, ok, skip_full_fetch = await _fetch_one_camera_events(
            coordinator, CAM_ID, session, HEADERS
        )

        assert events == [{"id": "evt-1"}]
        assert ok is True
        assert skip_full_fetch is False

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(aiohttp.ClientError("boom"), id="client-error"),
            pytest.param(TimeoutError(), id="timeout"),
            pytest.param(ValueError("bad json"), id="value-error"),
        ],
    )
    @pytest.mark.asyncio
    async def test_last_event_check_error_falls_back_to_full_fetch(
        self, exc: Exception
    ) -> None:
        """A transient last_event-check error falls back to the full fetch, not a failure."""
        coordinator = _make_coordinator()
        full_resp = _resp_cm(200, [{"id": "evt-1"}])
        session = MagicMock()
        session.get = MagicMock(side_effect=[exc, full_resp])

        _, events, ok, skip_full_fetch = await _fetch_one_camera_events(
            coordinator, CAM_ID, session, HEADERS
        )

        assert events == [{"id": "evt-1"}]
        assert ok is True
        assert skip_full_fetch is False

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(aiohttp.ClientError("boom"), id="client-error"),
            pytest.param(TimeoutError(), id="timeout"),
            pytest.param(ValueError("bad json"), id="value-error"),
        ],
    )
    @pytest.mark.asyncio
    async def test_full_fetch_error_returns_not_ok(self, exc: Exception) -> None:
        """A transient error on the full-fetch call itself must return ok=False."""
        coordinator = _make_coordinator()
        session = MagicMock()
        session.get = MagicMock(side_effect=[_resp_cm(404), exc])

        _, events, ok, skip_full_fetch = await _fetch_one_camera_events(
            coordinator, CAM_ID, session, HEADERS
        )

        assert events == []
        assert ok is False
        assert skip_full_fetch is False

    @pytest.mark.asyncio
    async def test_full_fetch_non_200_returns_not_ok(self) -> None:
        """A non-200 full-fetch response must return ok=False, empty events."""
        coordinator = _make_coordinator()
        session = MagicMock()
        session.get = MagicMock(side_effect=[_resp_cm(404), _resp_cm(500)])

        _, events, ok, _ = await _fetch_one_camera_events(
            coordinator, CAM_ID, session, HEADERS
        )

        assert events == []
        assert ok is False


class TestPollEvents:
    """`poll_events`'s gating + cache-write-vs-clobber-avoidance logic."""

    @pytest.mark.asyncio
    async def test_do_events_false_is_a_noop(self) -> None:
        """do_events=False skips the whole gather pass, no cache writes."""
        coordinator = _make_coordinator()
        session = MagicMock()

        result = await poll_events(coordinator, [CAM_ID], session, HEADERS, False)

        assert result is False
        session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_fresh_full_fetch_updates_cache_and_returns_true(self) -> None:
        """A definitive full fetch overwrites cached_events and reports fetched=True."""
        coordinator = _make_coordinator()
        session = MagicMock()
        session.get = MagicMock(
            side_effect=[_resp_cm(404), _resp_cm(200, [{"id": "evt-1"}])]
        )

        result = await poll_events(coordinator, [CAM_ID], session, HEADERS, True)

        assert result is True
        assert coordinator.cached_events[CAM_ID] == [{"id": "evt-1"}]

    @pytest.mark.asyncio
    async def test_skip_full_fetch_snapshot_does_not_clobber_cache(self) -> None:
        """A skip_full_fetch snapshot must not overwrite a concurrently-updated cache."""
        coordinator = _make_coordinator(
            last_event_ids={CAM_ID: "evt-1"},
            cached_events={CAM_ID: [{"id": "evt-1"}]},
        )
        session = MagicMock()
        session.get = MagicMock(return_value=_resp_cm(200, {"id": "evt-1"}))

        # Simulate a concurrent FCM push landing newer data mid-poll.
        coordinator.cached_events[CAM_ID] = [{"id": "evt-2"}]

        result = await poll_events(coordinator, [CAM_ID], session, HEADERS, True)

        assert result is True
        # The newer FCM-pushed data must survive, not get reaffirmed-clobbered.
        assert coordinator.cached_events[CAM_ID] == [{"id": "evt-2"}]

    @pytest.mark.asyncio
    async def test_transient_failure_keeps_previous_cache_and_reports_false(
        self,
    ) -> None:
        """A transient per-camera failure must not blank the cache nor report success."""
        coordinator = _make_coordinator(cached_events={CAM_ID: [{"id": "evt-old"}]})
        session = MagicMock()
        session.get = MagicMock(side_effect=[_resp_cm(404), _resp_cm(500)])

        result = await poll_events(coordinator, [CAM_ID], session, HEADERS, True)

        assert result is False
        assert coordinator.cached_events[CAM_ID] == [{"id": "evt-old"}]

    @pytest.mark.asyncio
    async def test_one_camera_exception_does_not_abort_the_others(self) -> None:
        """`return_exceptions=True` — one camera raising must not stop the rest."""
        coordinator = _make_coordinator()
        cam_ok = "cam-ok"
        cam_broken = "cam-broken"

        def _get_side_effect(url: str, **_kwargs: object) -> MagicMock:
            if cam_broken in url:
                raise RuntimeError("boom")
            if "last_event" in url:
                return _resp_cm(404)
            return _resp_cm(200, [{"id": "evt-1"}])

        session = MagicMock()
        session.get = MagicMock(side_effect=_get_side_effect)

        result = await poll_events(
            coordinator, [cam_ok, cam_broken], session, HEADERS, True
        )

        assert result is True
        assert coordinator.cached_events[cam_ok] == [{"id": "evt-1"}]
        assert cam_broken not in coordinator.cached_events
