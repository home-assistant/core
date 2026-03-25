"""Tests for Span Panel binary sensor entities and setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.span_panel.binary_sensor import (
    BESS_CONNECTED_SENSOR,
    BINARY_SENSORS,
    EVSE_BINARY_SENSORS,
    GRID_ISLANDABLE_SENSOR,
    SpanEvseBinarySensor,
    SpanPanelBinarySensor,
    async_setup_entry,
)
from homeassistant.components.span_panel.const import (
    DOMAIN,
    PANEL_STATUS,
    SYSTEM_DOOR_STATE,
)
from homeassistant.core import HomeAssistant

from .factories import (
    SpanBatterySnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
)

from tests.common import MockConfigEntry


def _make_coordinator(snapshot) -> MagicMock:
    """Create a coordinator-like mock for binary sensor tests."""
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.panel_offline = False
    coordinator.last_update_success = True
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        title="SPAN Panel",
        unique_id=snapshot.serial_number,
    )
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def test_panel_status_sensor_stays_available_when_panel_goes_offline() -> None:
    """The panel status binary sensor stays available and flips off when offline."""
    snapshot = SpanPanelSnapshotFactory.create()
    coordinator = _make_coordinator(snapshot)
    description = next(desc for desc in BINARY_SENSORS if desc.key == PANEL_STATUS)
    entity = SpanPanelBinarySensor(coordinator, description)
    entity.async_write_ha_state = MagicMock()

    coordinator.panel_offline = False
    entity._handle_coordinator_update()
    assert entity.available is True
    assert entity.is_on is True

    coordinator.panel_offline = True
    entity._handle_coordinator_update()
    assert entity.available is True
    assert entity.is_on is False


def test_hardware_status_sensor_shows_unknown_when_panel_offline() -> None:
    """Door/ethernet/wifi sensors stay available but report unknown offline."""
    snapshot = SpanPanelSnapshotFactory.create()
    coordinator = _make_coordinator(snapshot)
    coordinator.panel_offline = True
    description = next(desc for desc in BINARY_SENSORS if desc.key == SYSTEM_DOOR_STATE)
    entity = SpanPanelBinarySensor(coordinator, description)
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.available is True
    assert entity.is_on is None


def test_evse_binary_sensor_reports_unknown_when_panel_offline() -> None:
    """EVSE binary sensors should clear state when the panel is offline."""
    snapshot = SpanPanelSnapshotFactory.create(
        evse={"evse-0": SpanEvseSnapshotFactory.create(status="CHARGING")}
    )
    coordinator = _make_coordinator(snapshot)
    coordinator.panel_offline = True
    description = next(
        desc for desc in EVSE_BINARY_SENSORS if desc.key == "evse_charging"
    )
    entity = SpanEvseBinarySensor(coordinator, description, "evse-0")
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.is_on is None


def test_grid_islandable_sensor_uses_online_status_value() -> None:
    """Non-status binary sensors should mirror their live boolean value when online."""
    snapshot = SpanPanelSnapshotFactory.create(grid_islandable=False)
    coordinator = _make_coordinator(snapshot)
    entity = SpanPanelBinarySensor(coordinator, GRID_ISLANDABLE_SENSOR)
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.is_on is False
    assert entity.available is True


def test_bess_connected_sensor_becomes_unavailable_when_panel_offline() -> None:
    """Non-status binary sensors should become unavailable when the panel is offline."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(soe_percentage=85.0, connected=True)
    )
    coordinator = _make_coordinator(snapshot)
    coordinator.panel_offline = True
    entity = SpanPanelBinarySensor(coordinator, BESS_CONNECTED_SENSOR)
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.available is False


def test_binary_sensor_with_none_value_becomes_unavailable() -> None:
    """Binary sensors should be unavailable when their value function returns None."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(soe_percentage=85.0, connected=None)
    )
    coordinator = _make_coordinator(snapshot)
    entity = SpanPanelBinarySensor(coordinator, BESS_CONNECTED_SENSOR)
    entity.async_write_ha_state = MagicMock()

    entity._handle_coordinator_update()

    assert entity.is_on is None
    assert entity.available is False


def test_evse_binary_sensor_uses_empty_snapshot_when_missing_mid_session() -> None:
    """EVSE binary sensors should tolerate the charger disappearing from coordinator data."""
    snapshot = SpanPanelSnapshotFactory.create(
        evse={"evse-0": SpanEvseSnapshotFactory.create(status="CHARGING")}
    )
    coordinator = _make_coordinator(snapshot)
    description = next(
        desc for desc in EVSE_BINARY_SENSORS if desc.key == "evse_ev_connected"
    )
    entity = SpanEvseBinarySensor(coordinator, description, "evse-0")
    entity.async_write_ha_state = MagicMock()

    coordinator.data = SpanPanelSnapshotFactory.create(evse={})
    entity._handle_coordinator_update()

    assert entity.is_on is False


async def test_binary_sensor_async_setup_entry_adds_panel_bess_and_evse_entities(
    hass: HomeAssistant,
) -> None:
    """Platform setup should add the expected binary sensor set and refresh once."""
    snapshot = SpanPanelSnapshotFactory.create(
        grid_islandable=True,
        battery=SpanBatterySnapshotFactory.create(soe_percentage=85.0, connected=True),
        evse={"evse-0": SpanEvseSnapshotFactory.create()},
    )
    coordinator = _make_coordinator(snapshot)
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, title="SPAN Panel")
    config_entry.runtime_data = MagicMock(coordinator=coordinator)
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 8
