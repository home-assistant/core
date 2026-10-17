"""Tests for the Elke27 integration."""

from elke27_lib import AreaState, PanelInfo, PanelSnapshot, TableInfo, ZoneState
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

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Elke27 integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def build_snapshot(
    *,
    areas: dict[int, AreaState] | None = None,
    zones: dict[int, ZoneState] | None = None,
    panel: PanelInfo | None = None,
    version: int = 1,
) -> PanelSnapshot:
    """Build a panel snapshot for tests."""
    return PanelSnapshot(
        panel=panel
        or PanelInfo(serial="1234", model="E27", firmware="1.0", panel_name="Panel"),
        table_info=TableInfo(),
        areas=areas or {},
        zones=zones or {},
        zone_definitions={},
        outputs={},
        output_definitions={},
        lights={},
        barriers={},
        locks={},
        thermostats={},
        version=version,
        updated_at=dt_util.utcnow(),
    )


def connection_state_changed_event(*, connected: bool) -> ConnectionStateChanged:
    """Build a connection state event."""
    return ConnectionStateChanged(
        kind=ConnectionStateChanged.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        connected=connected,
    )


def csm_snapshot_updated_event(snapshot: PanelSnapshot) -> CsmSnapshotUpdated:
    """Build a CSM snapshot updated event."""
    return CsmSnapshotUpdated(
        kind=CsmSnapshotUpdated.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        snapshot=snapshot,
    )


def domain_csm_changed_event(domain: str) -> DomainCsmChanged:
    """Build a domain CSM changed event."""
    return DomainCsmChanged(
        kind=DomainCsmChanged.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        csm_domain=domain,
    )


def table_csm_changed_event(domain: str) -> TableCsmChanged:
    """Build a table CSM changed event."""
    return TableCsmChanged(
        kind=TableCsmChanged.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        csm_domain=domain,
    )


def zone_status_updated_event(zone_id: int) -> ZoneStatusUpdated:
    """Build a zone status updated event."""
    return ZoneStatusUpdated(
        kind=ZoneStatusUpdated.KIND,
        at=UNSET_AT,
        seq=UNSET_SEQ,
        classification=UNSET_CLASSIFICATION,
        route=UNSET_ROUTE,
        session_id=UNSET_SESSION_ID,
        zone_id=zone_id,
        changed_fields=("open",),
    )
