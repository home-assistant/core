"""Tests for the Elke27 data update coordinator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping

_elke27_lib = ModuleType("elke27_lib")
_elke27_lib_events = ModuleType("elke27_lib.events")
_elke27_lib_types = ModuleType("elke27_lib.types")

UNSET_ROUTE = ("__unset__", "__unset__")
UNSET_AT = 0.0
UNSET_SEQ = None
UNSET_CLASSIFICATION = "UNKNOWN"
UNSET_SESSION_ID = None


@dataclass(frozen=True, slots=True)
class CsmSnapshot:
    domain_csms: Mapping[str, int]
    table_csms: Mapping[str, int]
    version: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CsmSnapshotUpdated:
    KIND = "csm_snapshot_updated"

    kind: str
    at: float
    seq: int | None
    classification: str
    route: tuple[str, str]
    session_id: int | None
    snapshot: CsmSnapshot


@dataclass(frozen=True, slots=True)
class DomainCsmChanged:
    KIND = "domain_csm_changed"

    kind: str
    at: float
    seq: int | None
    classification: str
    route: tuple[str, str]
    session_id: int | None
    domain: str
    old: int | None = None
    new: int = 0


@dataclass(frozen=True, slots=True)
class TableCsmChanged:
    KIND = "table_csm_changed"

    kind: str
    at: float
    seq: int | None
    classification: str
    route: tuple[str, str]
    session_id: int | None
    domain: str
    old: int | None = None
    new: int = 0


_elke27_lib_events.CsmSnapshotUpdated = CsmSnapshotUpdated
_elke27_lib_events.DomainCsmChanged = DomainCsmChanged
_elke27_lib_events.TableCsmChanged = TableCsmChanged
_elke27_lib_events.UNSET_ROUTE = UNSET_ROUTE
_elke27_lib_events.UNSET_AT = UNSET_AT
_elke27_lib_events.UNSET_SEQ = UNSET_SEQ
_elke27_lib_events.UNSET_CLASSIFICATION = UNSET_CLASSIFICATION
_elke27_lib_events.UNSET_SESSION_ID = UNSET_SESSION_ID
_elke27_lib_types.CsmSnapshot = CsmSnapshot
_elke27_lib.events = _elke27_lib_events
_elke27_lib.types = _elke27_lib_types

sys.modules.setdefault("elke27_lib", _elke27_lib)
sys.modules["elke27_lib.events"] = _elke27_lib_events
sys.modules["elke27_lib.types"] = _elke27_lib_types

import pytest

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
