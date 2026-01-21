"""Tests for the Elke27 data update coordinator."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from elke27_lib.events import (
    CsmSnapshotUpdated,
    DomainCsmChanged,
    TableCsmChanged,
    UNSET_AT,
    UNSET_CLASSIFICATION,
    UNSET_ROUTE,
    UNSET_SEQ,
    UNSET_SESSION_ID,
)
from elke27_lib.types import CsmSnapshot

from homeassistant.core import HomeAssistant

from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
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
            domain="zone",
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
            domain="zone",
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
            domain="zone",
        )
    )

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    assert hub.refresh_domains == ["zone"]
    assert coordinator.data.version == 1
