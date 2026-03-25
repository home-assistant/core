"""Tests for Span Panel sensor platform orchestration."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.span_panel.const import (
    DOMAIN,
    ENABLE_CIRCUIT_NET_ENERGY_SENSORS,
    ENABLE_PANEL_NET_ENERGY_SENSORS,
    ENABLE_UNMAPPED_CIRCUIT_SENSORS,
    USE_CIRCUIT_NUMBERS,
)
from homeassistant.components.span_panel.sensor import (
    _build_evse_device_info_map,
    async_setup_entry,
    create_battery_sensors,
    create_circuit_sensors,
    create_evse_sensors,
    create_native_sensors,
    create_panel_sensors,
    create_power_flow_sensors,
    create_unmapped_circuit_sensors,
)
from homeassistant.core import HomeAssistant

from .factories import (
    SpanBatterySnapshotFactory,
    SpanCircuitSnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
    SpanPVSnapshot,
)

from tests.common import MockConfigEntry


async def test_sensor_async_setup_entry_adds_entities_and_refreshes(
    hass: HomeAssistant,
) -> None:
    """Sensor platform setup should add entities and refresh."""
    snapshot = SpanPanelSnapshotFactory.create()
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.async_request_refresh = AsyncMock()
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="SPAN Panel")
    entry.runtime_data = MagicMock(coordinator=coordinator)
    entities = [MagicMock(), MagicMock()]
    async_add_entities = MagicMock()

    with patch(
        "homeassistant.components.span_panel.sensor.create_native_sensors",
        return_value=entities,
    ) as mock_create:
        await async_setup_entry(hass, entry, async_add_entities)

    mock_create.assert_called_once_with(coordinator, snapshot, entry)
    async_add_entities.assert_called_once_with(entities)
    coordinator.async_request_refresh.assert_awaited_once()


async def test_sensor_async_setup_entry_logs_and_reraises_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Setup errors should be logged and re-raised."""
    coordinator = MagicMock()
    coordinator.data = SpanPanelSnapshotFactory.create()
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="SPAN Panel")
    entry.runtime_data = MagicMock(coordinator=coordinator)

    caplog.set_level(logging.ERROR)

    with (
        patch(
            "homeassistant.components.span_panel.sensor.create_native_sensors",
            side_effect=RuntimeError("broken sensor setup"),
        ),
        pytest.raises(RuntimeError, match="broken sensor setup"),
    ):
        await async_setup_entry(hass, entry, MagicMock())

    assert "Error in async_setup_entry: broken sensor setup" in caplog.text


def test_create_native_sensors_concatenates_sensor_groups() -> None:
    """Native sensor creation should preserve group ordering."""
    coordinator = MagicMock()
    snapshot = SpanPanelSnapshotFactory.create()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title="SPAN Panel",
        options={ENABLE_UNMAPPED_CIRCUIT_SENSORS: True},
    )

    panel = [MagicMock(name="panel")]
    circuit = [MagicMock(name="circuit")]
    unmapped = [MagicMock(name="unmapped")]
    battery = [MagicMock(name="battery")]
    power_flow = [MagicMock(name="power_flow")]
    evse = [MagicMock(name="evse")]

    with (
        patch(
            "homeassistant.components.span_panel.sensor.create_panel_sensors",
            return_value=panel,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_circuit_sensors",
            return_value=circuit,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_unmapped_circuit_sensors",
            return_value=unmapped,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_battery_sensors",
            return_value=battery,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_power_flow_sensors",
            return_value=power_flow,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_evse_sensors",
            return_value=evse,
        ),
    ):
        result = create_native_sensors(coordinator, snapshot, entry)

    assert result == panel + circuit + unmapped + battery + power_flow + evse


def test_create_native_sensors_excludes_unmapped_when_disabled() -> None:
    """Unmapped sensors should be excluded when the option is disabled."""
    coordinator = MagicMock()
    snapshot = SpanPanelSnapshotFactory.create()
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="SPAN Panel")

    panel = [MagicMock(name="panel")]
    circuit = [MagicMock(name="circuit")]
    battery = [MagicMock(name="battery")]
    power_flow = [MagicMock(name="power_flow")]
    evse = [MagicMock(name="evse")]

    with (
        patch(
            "homeassistant.components.span_panel.sensor.create_panel_sensors",
            return_value=panel,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_circuit_sensors",
            return_value=circuit,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_unmapped_circuit_sensors",
        ) as mock_unmapped,
        patch(
            "homeassistant.components.span_panel.sensor.create_battery_sensors",
            return_value=battery,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_power_flow_sensors",
            return_value=power_flow,
        ),
        patch(
            "homeassistant.components.span_panel.sensor.create_evse_sensors",
            return_value=evse,
        ),
    ):
        result = create_native_sensors(coordinator, snapshot, entry)

    mock_unmapped.assert_not_called()
    assert result == panel + circuit + battery + power_flow + evse


def test_create_panel_sensors_filters_net_energy_and_adds_diagnostics() -> None:
    """Panel sensors should honor net-energy options and optional diagnostics."""
    snapshot = SpanPanelSnapshotFactory.create(
        l1_voltage=120.0,
        l2_voltage=121.0,
        upstream_l1_current_a=10.0,
        upstream_l2_current_a=11.0,
        downstream_l1_current_a=12.0,
        downstream_l2_current_a=13.0,
        main_breaker_rating_a=200,
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title="SPAN Panel",
        options={ENABLE_PANEL_NET_ENERGY_SENSORS: False},
        unique_id=snapshot.serial_number,
    )
    coordinator.config_entry = entry

    entities = create_panel_sensors(coordinator, snapshot, entry)
    keys = [entity.entity_description.key for entity in entities]

    assert "mainMeterNetEnergyWh" not in keys
    assert "feedthroughNetEnergyWh" not in keys
    assert "l1_voltage" in keys
    assert "l2_voltage" in keys
    assert "upstream_l1_current" in keys
    assert "upstream_l2_current" in keys
    assert "downstream_l1_current" in keys
    assert "downstream_l2_current" in keys
    assert "main_breaker_rating" in keys


def test_build_evse_device_info_map_uses_feed_circuit_and_display_suffix() -> None:
    """EVSE feed circuits should map to EVSE sub-device info."""
    snapshot = SpanPanelSnapshotFactory.create(
        circuits={
            "c1": SpanCircuitSnapshotFactory.create(
                circuit_id="c1", name="Garage Charger"
            )
        },
        evse={
            "evse-0": SpanEvseSnapshotFactory.create(
                node_id="evse-0", feed_circuit_id="c1"
            )
        },
    )
    coordinator = MagicMock()
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"device_name": "Main House"},
        title="SPAN Panel",
        options={USE_CIRCUIT_NUMBERS: False},
    )

    mapping = _build_evse_device_info_map(coordinator, snapshot)

    assert list(mapping) == ["c1"]
    assert mapping["c1"]["name"] == "Main House SPAN Drive (Garage Charger)"


def test_create_circuit_sensors_skips_unmapped_and_optional_net_sensors() -> None:
    """Circuit sensors should ignore unmapped tabs and honor net-energy options."""
    snapshot = SpanPanelSnapshotFactory.create(
        circuits={
            "c1": SpanCircuitSnapshotFactory.create(
                circuit_id="c1",
                name="Kitchen",
                current_a=10.0,
                breaker_rating_a=20.0,
            ),
            "unmapped_tab_7": SpanCircuitSnapshotFactory.create(
                circuit_id="unmapped_tab_7"
            ),
        },
        evse={
            "evse-0": SpanEvseSnapshotFactory.create(
                node_id="evse-0", feed_circuit_id="c1"
            )
        },
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"device_name": "Main House"},
        title="SPAN Panel",
        options={ENABLE_CIRCUIT_NET_ENERGY_SENSORS: False},
        unique_id=snapshot.serial_number,
    )
    coordinator.config_entry = entry

    entities = create_circuit_sensors(coordinator, snapshot, entry)
    keys = [entity.original_key for entity in entities]
    circuit_ids = [entity.circuit_id for entity in entities]

    assert "c1" in circuit_ids
    assert "unmapped_tab_7" not in circuit_ids
    assert "circuit_energy_net" not in keys
    assert "circuit_current" in keys
    assert "circuit_breaker_rating" in keys
    assert any(
        entity.device_info["name"] == "Main House SPAN Drive (Kitchen)"
        for entity in entities
    )


def test_create_unmapped_circuit_sensors_only_creates_unmapped_entities() -> None:
    """Unmapped helper sensors should only be created for unmapped circuits."""
    snapshot = SpanPanelSnapshotFactory.create(
        circuits={
            "c1": SpanCircuitSnapshotFactory.create(circuit_id="c1"),
            "unmapped_tab_7": SpanCircuitSnapshotFactory.create(
                circuit_id="unmapped_tab_7"
            ),
        }
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, title="SPAN Panel"
    )

    entities = create_unmapped_circuit_sensors(coordinator, snapshot)

    assert len(entities) == 3
    assert all(entity.circuit_id == "unmapped_tab_7" for entity in entities)


def test_create_battery_sensors_returns_expected_entities_when_bess_present() -> None:
    """Battery helpers should create battery power, SoE, and metadata sensors."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(
            soe_percentage=75.0, vendor_name="Tesla", product_name="Powerwall"
        )
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"device_name": "Main House"},
        title="SPAN Panel",
    )

    entities = create_battery_sensors(coordinator, snapshot)
    keys = [entity.entity_description.key for entity in entities]

    assert len(entities) == 8
    assert "batteryPowerW" in keys
    assert "storage_battery_percentage" in keys
    assert "vendor" in keys


def test_create_power_flow_sensors_gate_pv_and_site_flow() -> None:
    """Power-flow helper should add PV and site/grid entities only when available."""
    snapshot = SpanPanelSnapshotFactory.create(
        power_flow_pv=-3500.0,
        power_flow_grid=-1200.0,
        power_flow_site=2400.0,
        pv=SpanPVSnapshot(vendor_name="SolarEdge"),
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, title="SPAN Panel"
    )

    entities = create_power_flow_sensors(coordinator, snapshot)
    keys = [entity.entity_description.key for entity in entities]

    assert "pvPowerW" in keys
    assert "gridPowerFlowW" in keys
    assert "sitePowerW" in keys
    assert "pv_vendor" in keys


def test_create_evse_sensors_creates_all_descriptions_for_each_charger() -> None:
    """EVSE helpers should create one entity per EVSE description."""
    snapshot = SpanPanelSnapshotFactory.create(
        evse={
            "evse-0": SpanEvseSnapshotFactory.create(node_id="evse-0"),
            "evse-1": SpanEvseSnapshotFactory.create(node_id="evse-1"),
        }
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, title="SPAN Panel"
    )

    entities = create_evse_sensors(coordinator, snapshot)

    assert len(entities) == 6
    assert {entity._evse_id for entity in entities} == {"evse-0", "evse-1"}
