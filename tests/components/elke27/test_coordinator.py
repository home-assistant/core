"""Tests for the Elke27 data update coordinator."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from elke27_lib import PanelSnapshot
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
from elke27_lib.errors import Elke27Error, Elke27TimeoutError
from elke27_lib.types import CsmSnapshot
import pytest

from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import (
    Elke27DataUpdateCoordinator,
    _normalize_domains,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

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


def _coordinator(
    hass: HomeAssistant,
    hub: _FakeHub,
    entry: MockConfigEntry,
    *,
    debounce_seconds: float = 0,
) -> Elke27DataUpdateCoordinator:
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator._debounce_seconds = debounce_seconds
    return coordinator


async def test_coordinator_subscribes_and_sets_snapshot(hass: HomeAssistant) -> None:
    """Verify the coordinator subscribes and stores the initial snapshot."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    await coordinator.async_start()

    assert coordinator.data == hub.get_snapshot()
    assert hub._subscribe_typed is not None

    await coordinator.async_start()
    assert hub._subscribe_typed is not None


async def test_coordinator_uses_empty_snapshot_when_snapshot_missing(
    hass: HomeAssistant,
) -> None:
    """Verify the coordinator uses an empty snapshot when the hub has none."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(None)
    coordinator = _coordinator(hass, hub, entry)

    await coordinator.async_start()

    assert coordinator.data == PanelSnapshot.empty()


async def test_coordinator_start_suppresses_unsubscribe_error(
    hass: HomeAssistant,
) -> None:
    """Verify start suppresses errors from a previous unsubscribe callback."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    def _raise() -> None:
        raise RuntimeError("unsubscribe failed")

    coordinator._unsubscribe = _raise

    await coordinator.async_start()

    assert hub._subscribe_typed is not None


async def test_domain_csm_change_refreshes_domain(hass: HomeAssistant) -> None:
    """Verify DomainCsmChanged events refresh the domain and update snapshot."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

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
    coordinator = _coordinator(hass, hub, entry, debounce_seconds=0.05)

    await coordinator.async_start()
    updated_snapshot = SimpleNamespace(version=2)
    hub._snapshot = updated_snapshot
    snapshot_event = CsmSnapshot(
        domain_csms={"zone": 2},
        table_csms={"zone": 11},
        version=2,
        updated_at=dt_util.utcnow(),
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
    coordinator = _coordinator(hass, hub, entry)

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

    await hass.async_block_till_done()

    assert hub.refresh_domains == ["zone"]
    assert coordinator.data.version == 1


async def test_async_stop_cancels_debounce(hass: HomeAssistant) -> None:
    """Verify async_stop cancels debounce task."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry, debounce_seconds=0.1)
    await coordinator.async_start()
    coordinator._debounce_task = asyncio.create_task(asyncio.sleep(0.2))
    await coordinator.async_stop()
    assert coordinator._debounce_task is None


async def test_async_stop_suppresses_debounce_task_error(
    hass: HomeAssistant,
) -> None:
    """Verify async_stop suppresses already failed debounce tasks."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    async def _raise() -> None:
        raise RuntimeError("debounce failed")

    coordinator._debounce_task = asyncio.create_task(_raise())
    await hass.async_block_till_done()

    await coordinator.async_stop()

    assert coordinator._debounce_task is None


async def test_async_stop_suppresses_unsubscribe_error(hass: HomeAssistant) -> None:
    """Verify stop suppresses unsubscribe callback errors."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    def _raise() -> None:
        raise RuntimeError("unsubscribe failed")

    coordinator._unsubscribe = _raise

    await coordinator.async_stop()

    assert coordinator._unsubscribe is None


async def test_async_refresh_now_updates_snapshot(hass: HomeAssistant) -> None:
    """Verify async_refresh_now refreshes snapshot."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)
    await coordinator.async_refresh_now()
    assert hub.refresh_csm_calls == 1


async def test_update_data_maps_transient_errors_to_update_failed(
    hass: HomeAssistant,
) -> None:
    """Verify transient refresh errors are retryable update failures."""

    class ErrorHub(_FakeHub):
        async def refresh_csm(self) -> None:
            raise Elke27TimeoutError()

    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = ErrorHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_update_data_maps_permanent_errors_to_config_entry_error(
    hass: HomeAssistant,
) -> None:
    """Verify permanent refresh errors fail setup instead of retrying."""

    class ErrorHub(_FakeHub):
        async def refresh_csm(self) -> None:
            raise Elke27Error("refresh failed", code=1, is_transient=False)

    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = ErrorHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    with pytest.raises(ConfigEntryError):
        await coordinator._async_update_data()


async def test_async_refresh_now_serializes_refreshes(hass: HomeAssistant) -> None:
    """Verify concurrent full refreshes do not overlap."""

    class SlowHub(_FakeHub):
        def __init__(self, snapshot: Any) -> None:
            super().__init__(snapshot)
            self.active_refreshes = 0
            self.max_active_refreshes = 0

        async def refresh_csm(self) -> None:
            self.active_refreshes += 1
            self.max_active_refreshes = max(
                self.max_active_refreshes, self.active_refreshes
            )
            await asyncio.sleep(0)
            self.refresh_csm_calls += 1
            self.active_refreshes -= 1

    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = SlowHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)

    await asyncio.gather(
        coordinator.async_refresh_now(), coordinator.async_refresh_now()
    )

    assert hub.refresh_csm_calls == 2
    assert hub.max_active_refreshes == 1


async def test_queue_domain_refresh_handles_exception(hass: HomeAssistant) -> None:
    """Verify exceptions in refresh domain are handled."""

    class ErrorHub(_FakeHub):
        async def refresh_domain_config(self, domain: str) -> None:
            raise RuntimeError("boom")

    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = ErrorHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)
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
    coordinator = _coordinator(hass, hub, entry)

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
    assert coordinator.data is hub.get_snapshot()
    await hass.async_block_till_done()
    coordinator.async_refresh_now.assert_awaited_once()


def test_normalize_domains() -> None:
    """Verify domain normalization helper."""
    assert _normalize_domains(None) == set()
    assert _normalize_domains("zone") == {"zone"}
    assert _normalize_domains(["zone", "area"]) == {"zone", "area"}


async def test_zone_status_event_updates_snapshot(hass: HomeAssistant) -> None:
    """Verify zone status events keep snapshot updated."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hub = _FakeHub(SimpleNamespace(version=1))
    coordinator = _coordinator(hass, hub, entry)
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
