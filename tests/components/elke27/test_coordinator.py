"""Tests for the Elke27 data update coordinator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.core import HomeAssistant

from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27 import coordinator as coordinator_module
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from tests.common import MockConfigEntry


@dataclass(frozen=True, slots=True)
class _CsmSnapshot:
    domain_csms: dict[str, int]
    table_csms: dict[str, int]


class CsmSnapshotUpdated:
    def __init__(self, snapshot: _CsmSnapshot) -> None:
        self.snapshot = snapshot


class DomainCsmChanged:
    def __init__(self, domain: str) -> None:
        self.domain = domain


class TableCsmChanged:
    def __init__(self, domain: str) -> None:
        self.domain = domain


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


@pytest.fixture(autouse=True)
def _force_fallback_event_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force fallback matching so test event classes are recognized."""
    monkeypatch.setattr(coordinator_module, "CsmSnapshotUpdated", None)
    monkeypatch.setattr(coordinator_module, "DomainCsmChanged", None)
    monkeypatch.setattr(coordinator_module, "TableCsmChanged", None)


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
    hub.emit(DomainCsmChanged("zone"))
    await hass.async_block_till_done()

    assert hub.refresh_domains == ["zone"]
    assert coordinator.data.version == 1


async def test_csm_snapshot_event_updates_data(hass: HomeAssistant) -> None:
    """Verify CSM snapshot updates replace coordinator data."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0.05)

    await coordinator.async_start()
    snapshot = _CsmSnapshot({"zone": 2}, {"zone": 11})
    hub.emit(CsmSnapshotUpdated(snapshot))
    await hass.async_block_till_done()

    assert coordinator.data == snapshot


async def test_csm_change_event_coalesces_refresh(hass: HomeAssistant) -> None:
    """Verify CSM change events are debounced and coalesced."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry, debounce_seconds=0.05)

    await coordinator.async_start()
    hub.emit(DomainCsmChanged("zone"))
    hub.emit(TableCsmChanged("zone"))

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    assert hub.refresh_domains == ["zone"]
    assert coordinator.data.version == 1
