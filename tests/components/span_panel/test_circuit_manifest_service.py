"""Tests for the export_circuit_manifest service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.span_panel import (
    SpanPanelRuntimeData,
    _async_register_services,
)
from homeassistant.components.span_panel.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .factories import SpanCircuitSnapshotFactory, SpanPanelSnapshotFactory

from tests.common import MockConfigEntry


def _make_coordinator(snapshot):
    """Create a mock coordinator wrapping a snapshot."""
    coordinator = MagicMock()
    coordinator.data = snapshot
    return coordinator


def _register_power_entity(
    hass: HomeAssistant,
    config_entry_id: str,
    serial: str,
    circuit_id: str,
    suggested_entity_id: str,
) -> er.RegistryEntry:
    """Register a circuit power sensor entity in the entity registry."""
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    entity_registry = er.async_get(hass)
    unique_id = f"span_{serial.lower()}_{circuit_id}_power"
    return entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        unique_id,
        config_entry=config_entry,
        suggested_object_id=suggested_entity_id.split(".", 1)[1],
    )


async def _call_manifest_service(hass: HomeAssistant):
    """Call the export_circuit_manifest service and return the response."""
    return await hass.services.async_call(
        DOMAIN,
        "export_circuit_manifest",
        {},
        blocking=True,
        return_response=True,
    )


class TestExportCircuitManifest:
    """Tests for the export_circuit_manifest service."""

    @pytest.mark.asyncio
    async def test_basic_manifest(self, hass: HomeAssistant):
        """Returns correct manifest for a panel with circuits."""
        kitchen = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_kitchen",
            name="Kitchen",
            tabs=[2, 3],
        )
        bedroom = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_bedroom",
            name="Bedroom",
            tabs=[5],
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-test-001",
            circuits={"uuid_kitchen": kitchen, "uuid_bedroom": bedroom},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100"},
            entry_id="span_entry",
            unique_id="sp3-test-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        _register_power_entity(
            hass,
            "span_entry",
            "sp3-test-001",
            "uuid_kitchen",
            "sensor.span_panel_kitchen_power",
        )
        _register_power_entity(
            hass,
            "span_entry",
            "sp3-test-001",
            "uuid_bedroom",
            "sensor.span_panel_bedroom_power",
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        assert result is not None
        assert len(result["panels"]) == 1

        panel = result["panels"][0]
        assert panel["serial"] == "sp3-test-001"
        assert panel["host"] == "192.168.1.100"
        assert len(panel["circuits"]) == 2

        by_template = {c["template"]: c for c in panel["circuits"]}

        assert by_template["clone_2"]["device_type"] == "circuit"
        assert by_template["clone_2"]["tabs"] == [2, 3]
        assert by_template["clone_2"]["entity_id"].endswith("_kitchen_power")

        assert by_template["clone_5"]["device_type"] == "circuit"
        assert by_template["clone_5"]["tabs"] == [5]
        assert by_template["clone_5"]["entity_id"].endswith("_bedroom_power")

    @pytest.mark.asyncio
    async def test_multiple_panels(self, hass: HomeAssistant):
        """Returns manifests for all loaded panels."""
        circuit_a = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_a",
            tabs=[1],
        )
        circuit_b = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_b",
            tabs=[3],
        )
        snapshot_a = SpanPanelSnapshotFactory.create(
            serial_number="serial-aaa",
            circuits={"uuid_a": circuit_a},
        )
        snapshot_b = SpanPanelSnapshotFactory.create(
            serial_number="serial-bbb",
            circuits={"uuid_b": circuit_b},
        )

        entry_a = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100"},
            entry_id="entry_a",
            unique_id="serial-aaa",
        )
        entry_b = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.101"},
            entry_id="entry_b",
            unique_id="serial-bbb",
        )
        entry_a.add_to_hass(hass)
        entry_b.add_to_hass(hass)
        entry_a.mock_state(hass, ConfigEntryState.LOADED)
        entry_b.mock_state(hass, ConfigEntryState.LOADED)
        entry_a.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot_a)
        )
        entry_b.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot_b)
        )

        _register_power_entity(
            hass, "entry_a", "serial-aaa", "uuid_a", "sensor.panel_a_power"
        )
        _register_power_entity(
            hass, "entry_b", "serial-bbb", "uuid_b", "sensor.panel_b_power"
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        assert result is not None
        serials = {p["serial"] for p in result["panels"]}
        assert serials == {"serial-aaa", "serial-bbb"}

        by_serial = {p["serial"]: p for p in result["panels"]}
        assert by_serial["serial-aaa"]["host"] == "192.168.1.100"
        assert by_serial["serial-bbb"]["host"] == "192.168.1.101"

    @pytest.mark.asyncio
    async def test_unmapped_tabs_excluded(self, hass: HomeAssistant):
        """Unmapped tab circuits are excluded from the manifest."""
        real = SpanCircuitSnapshotFactory.create(circuit_id="uuid_real", tabs=[1])
        unmapped = SpanCircuitSnapshotFactory.create(
            circuit_id="unmapped_tab_5", tabs=[5]
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={"uuid_real": real, "unmapped_tab_5": unmapped},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.1"},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_real", "sensor.real_power"
        )
        _register_power_entity(
            hass,
            "span_entry",
            "sp3-001",
            "unmapped_tab_5",
            "sensor.unmapped_power",
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        panel = result["panels"][0]
        templates = [c["template"] for c in panel["circuits"]]
        assert "clone_1" in templates
        assert "clone_5" not in templates

    @pytest.mark.asyncio
    async def test_circuit_without_entity_excluded(self, hass: HomeAssistant):
        """Circuits with no registered power entity are excluded."""
        registered = SpanCircuitSnapshotFactory.create(circuit_id="uuid_reg", tabs=[1])
        unregistered = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_unreg", tabs=[3]
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={"uuid_reg": registered, "uuid_unreg": unregistered},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.1"},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        # Only register entity for one circuit
        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_reg", "sensor.reg_power"
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        panel = result["panels"][0]
        assert len(panel["circuits"]) == 1
        assert panel["circuits"][0]["template"] == "clone_1"

    @pytest.mark.asyncio
    async def test_no_loaded_entries_raises_validation_error(self, hass: HomeAssistant):
        """Raises ServiceValidationError when no config entries are loaded."""
        _async_register_services(hass)

        with pytest.raises(ServiceValidationError) as excinfo:
            await _call_manifest_service(hass)
        assert excinfo.value.translation_key == "export_manifest_no_entries"
        assert excinfo.value.translation_domain == DOMAIN

    @pytest.mark.asyncio
    async def test_all_device_types_included(self, hass: HomeAssistant):
        """All device types are included — PV, BESS, EVSE, and regular circuits."""
        regular = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_reg",
            tabs=[1],
            device_type="circuit",
        )
        pv = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_pv",
            tabs=[5],
            device_type="pv",
        )
        evse = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_evse",
            tabs=[10, 12],
            device_type="evse",
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={
                "uuid_reg": regular,
                "uuid_pv": pv,
                "uuid_evse": evse,
            },
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.1"},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_reg", "sensor.reg_power"
        )
        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_pv", "sensor.pv_power"
        )
        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_evse", "sensor.evse_power"
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        panel = result["panels"][0]
        assert len(panel["circuits"]) == 3

        by_template = {c["template"]: c for c in panel["circuits"]}
        assert by_template["clone_1"]["device_type"] == "circuit"
        assert by_template["clone_5"]["device_type"] == "pv"
        assert by_template["clone_10"]["device_type"] == "evse"

    @pytest.mark.asyncio
    async def test_bess_device_type_mapped_to_battery(self, hass: HomeAssistant):
        """Internal 'bess' device type is mapped to 'battery' in the manifest."""
        bess = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_bess",
            tabs=[14, 16],
            device_type="bess",
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={"uuid_bess": bess},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.1"},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_bess", "sensor.bess_power"
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        panel = result["panels"][0]
        assert len(panel["circuits"]) == 1
        assert panel["circuits"][0]["device_type"] == "battery"
        assert panel["circuits"][0]["template"] == "clone_14"
        assert panel["circuits"][0]["tabs"] == [14, 16]

    @pytest.mark.asyncio
    async def test_panel_with_no_resolvable_circuits_omitted(self, hass: HomeAssistant):
        """Panel where no circuits have registered entities is omitted."""
        circuit = SpanCircuitSnapshotFactory.create(circuit_id="uuid_orphan", tabs=[1])
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={"uuid_orphan": circuit},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )
        # No entities registered

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        assert result["panels"] == []

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_template_uses_min_tab(self, hass: HomeAssistant):
        """Template name is clone_{min(tabs)}, not max or first."""
        circuit = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_240v",
            tabs=[8, 6],
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={"uuid_240v": circuit},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.1"},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_240v", "sensor.c_power"
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        circuit_data = result["panels"][0]["circuits"][0]
        assert circuit_data["template"] == "clone_6"
        assert circuit_data["tabs"] == [8, 6]

    @pytest.mark.asyncio
    async def test_host_included_from_config_entry(self, hass: HomeAssistant):
        """Host field is populated from config entry data."""
        circuit = SpanCircuitSnapshotFactory.create(circuit_id="uuid_a", tabs=[1])
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-001",
            circuits={"uuid_a": circuit},
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "10.0.0.50"},
            entry_id="span_entry",
            unique_id="sp3-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        _register_power_entity(
            hass, "span_entry", "sp3-001", "uuid_a", "sensor.a_power"
        )

        _async_register_services(hass)
        result = await _call_manifest_service(hass)

        assert result["panels"][0]["host"] == "10.0.0.50"
