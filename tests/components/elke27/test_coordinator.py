"""Tests for the Elke27 data update coordinator."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from elke27_lib.events import (
    UNSET_AT,
    UNSET_CLASSIFICATION,
    UNSET_ROUTE,
    UNSET_SEQ,
    UNSET_SESSION_ID,
    ConnectionStateChanged,
    CsmSnapshotUpdated,
    DomainCsmChanged,
    TableCsmChanged,
    ZoneStatusUpdated,
)
from elke27_lib.types import CsmSnapshot

from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import (
    Elke27DataUpdateCoordinator,
    _is_event,
    _normalize_domains,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _FakeHub:
    def __init__(self, snapshot: Any) -> None:
        self._snapshot = snapshot
        self._subscribe: Any | None = None
        self._subscribe_typed: Any | None = None
        self.refresh_domains: list[str] = []
        self.refresh_csm_calls = 0

    def get_snapshot(self) -> Any:
        return self._snapshot

    def subscribe(self, callback: Any) -> Any:
        self._subscribe = callback

        def _unsub() -> None:
            self._subscribe = None

        return _unsub

    def subscribe_typed(self, callback: Any) -> Any:
        self._subscribe_typed = callback

        def _unsub() -> None:
            self._subscribe_typed = None

        return _unsub

    async def refresh_domain_config(self, domain: str) -> None:
        self.refresh_domains.append(domain)
        self._snapshot = SimpleNamespace(version=len(self.refresh_domains))

    async def refresh_csm(self) -> None:
        self.refresh_csm_calls += 1

    def emit(self, event: Any) -> None:
        if self._subscribe_typed is not None:
            self._subscribe_typed(event)


async def test_coordinator_subscribes_and_sets_snapshot(hass: HomeAssistant) -> None:
    """Verify the coordinator subscribes and stores the initial snapshot."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0)

    await coordinator.async_start()

    assert coordinator.data == hub.get_snapshot()
    assert hub._subscribe_typed is not None

    await coordinator.async_start()
    assert hub._subscribe_typed is not None


async def test_domain_csm_change_refreshes_domain(hass: HomeAssistant) -> None:
    """Verify DomainCsmChanged events refresh the domain and update snapshot."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0)

    await coordinator.async_start()
    hub.emit(
        DomainCsmChanged(
            kind=DomainCsmChanged.KIND,
            at=UNSET_AT,
            seq=UNSET_SEQ,
            classification=UNSET_CLASSIFICATION,
            route=UNSET_ROUTE,
            session_id=UNSET_SESSION_ID,
            csm_domain="zone",
        )
    )
    await hass.async_block_till_done()

    assert hub.refresh_domains == ["zone"]
    assert coordinator.data.version == 1


async def test_csm_snapshot_event_updates_data(hass: HomeAssistant) -> None:
    """Verify CSM snapshot updates replace coordinator data."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0.05)

    await coordinator.async_start()
    updated_snapshot = SimpleNamespace(version=2)
    hub._snapshot = updated_snapshot
    snapshot_event = CsmSnapshot(
        domain_csms={"zone": 2},
        table_csms={"zone": 11},
        version=2,
        updated_at=datetime.now(tz=UTC),
    )
    hub.emit(
        CsmSnapshotUpdated(
            kind=CsmSnapshotUpdated.KIND,
            at=UNSET_AT,
            seq=UNSET_SEQ,
            classification=UNSET_CLASSIFICATION,
            route=UNSET_ROUTE,
            session_id=UNSET_SESSION_ID,
            snapshot=snapshot_event,
        )
    )
    await hass.async_block_till_done()

    assert coordinator.data == updated_snapshot


async def test_csm_change_event_coalesces_refresh(hass: HomeAssistant) -> None:
    """Verify CSM change events are debounced and coalesced."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0.05)

    await coordinator.async_start()
    hub.emit(
        DomainCsmChanged(
            kind=DomainCsmChanged.KIND,
            at=UNSET_AT,
            seq=UNSET_SEQ,
            classification=UNSET_CLASSIFICATION,
            route=UNSET_ROUTE,
            session_id=UNSET_SESSION_ID,
            csm_domain="zone",
        )
    )
    hub.emit(
        TableCsmChanged(
            kind=TableCsmChanged.KIND,
            at=UNSET_AT,
            seq=UNSET_SEQ,
            classification=UNSET_CLASSIFICATION,
            route=UNSET_ROUTE,
            session_id=UNSET_SESSION_ID,
            csm_domain="zone",
        )
    )

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    assert hub.refresh_domains == ["zone"]
    assert coordinator.data.version == 1


async def test_async_stop_cancels_debounce(hass: HomeAssistant) -> None:
    """Verify async_stop cancels debounce task."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0.1)
    await coordinator.async_start()
    coordinator._debounce_task = asyncio.create_task(asyncio.sleep(0.2))
    await coordinator.async_stop()
    assert coordinator._debounce_task is None


async def test_async_refresh_now_updates_snapshot(hass: HomeAssistant) -> None:
    """Verify async_refresh_now refreshes snapshot."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0)
    await coordinator.async_refresh_now()
    assert hub.refresh_csm_calls == 1


async def test_queue_domain_refresh_handles_exception(hass: HomeAssistant) -> None:
    """Verify exceptions in refresh domain are handled."""

    class ErrorHub(_FakeHub):
        async def refresh_domain_config(self, domain: str) -> None:
            raise RuntimeError("boom")

    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = ErrorHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0)
    await coordinator.async_start()
    coordinator._queue_domain_refresh({"zone"})
    await asyncio.sleep(0)
    await hass.async_block_till_done()


async def test_connection_state_event_triggers_refresh(
    hass: HomeAssistant,
) -> None:
    """Verify connection state events schedule a refresh."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0)

    await coordinator.async_start()
    coordinator.async_refresh_now = AsyncMock()

    def _create_task(coro):  # type: ignore[no-untyped-def]
        return asyncio.create_task(coro)

    hass.async_create_task = _create_task  # type: ignore[assignment]

    event = ConnectionStateChanged(
        kind=ConnectionStateChanged.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        connected=True,
    )
    coordinator._process_event(event)
    await hass.async_block_till_done()
    coordinator.async_refresh_now.assert_awaited_once()


def test_is_event_fallback() -> None:
    """Verify event matching falls back to class name when needed."""

    class FakeEvent:
        pass

    event = FakeEvent()
    assert _is_event(event, None, "FakeEvent")


def test_normalize_domains() -> None:
    """Verify domain normalization helper."""
    assert _normalize_domains(None) == set()
    assert _normalize_domains("zone") == {"zone"}
    assert _normalize_domains(["zone", "area"]) == {"zone", "area"}


async def test_zone_status_event_updates_snapshot(hass: HomeAssistant) -> None:
    """Verify zone status events keep snapshot updated."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0)
    await coordinator.async_start()
    event = ZoneStatusUpdated(
        kind=ZoneStatusUpdated.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        zone_id=1,
        changed_fields=("open",),
    )
    coordinator._process_event(event)
