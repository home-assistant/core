"""Tests for the span_panel/panel_topology WebSocket command."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from homeassistant.components.span_panel import SpanPanelRuntimeData
from homeassistant.components.span_panel.const import DOMAIN
from homeassistant.components.span_panel.websocket import (
    _build_circuit_entity_map,
    _classify_sensor_role,
    _classify_sub_device,
    _find_config_entry_id,
    async_register_commands,
    handle_panel_topology,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .factories import (
    SpanBatterySnapshotFactory,
    SpanCircuitSnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
)

from tests.common import MockConfigEntry, MockUser
from tests.typing import WebSocketGenerator

# The command stack includes wrappers such as @async_response and
# @require_admin. Unwrap until we reach the original async handler so the
# direct-call tests can await it.
_handle_panel_topology_inner = handle_panel_topology
while not inspect.iscoroutinefunction(_handle_panel_topology_inner):
    _handle_panel_topology_inner = _handle_panel_topology_inner.__wrapped__

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_connection() -> MagicMock:
    """Create a mock WebSocket connection."""
    connection = MagicMock()
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()
    return connection


def _make_coordinator(snapshot):
    """Create a mock coordinator wrapping a snapshot."""
    coordinator = MagicMock()
    coordinator.data = snapshot
    return coordinator


def _register_panel_device(
    hass: HomeAssistant,
    config_entry_id: str,
    serial: str = "sp3-242424-001",
) -> dr.DeviceEntry:
    """Register a SPAN panel device in the device registry."""
    device_registry = dr.async_get(hass)
    return device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, serial)},
        manufacturer="Span",
        model="SPAN Panel",
        name="SPAN Panel",
    )


def _register_sub_device(
    hass: HomeAssistant,
    config_entry_id: str,
    identifier: str,
    name: str,
    via_device_id: str,
) -> dr.DeviceEntry:
    """Register a sub-device linked to a parent panel."""
    device_registry = dr.async_get(hass)
    dev = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, identifier)},
        name=name,
    )
    device_registry.async_update_device(dev.id, via_device_id=via_device_id)
    updated = device_registry.async_get(dev.id)
    assert updated is not None
    return updated


def _register_entity(
    hass: HomeAssistant,
    config_entry_id: str,
    device_id: str,
    domain: str,
    unique_id: str,
    entity_id: str,
    original_name: str | None = None,
) -> er.RegistryEntry:
    """Register an entity in the entity registry."""
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    entity_registry = er.async_get(hass)
    return entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        unique_id,
        config_entry=config_entry,
        device_id=device_id,
        original_name=original_name,
        suggested_object_id=entity_id.split(".", 1)[1]
        if "." in entity_id
        else entity_id,
    )


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestClassifySensorRole:
    """Tests for _classify_sensor_role."""

    def test_power(self):
        """Recognize circuit power sensor suffixes."""
        assert _classify_sensor_role("span_panel_kitchen_power") == "power"

    def test_produced_energy(self):
        """Recognize produced energy sensor suffixes."""
        assert (
            _classify_sensor_role("span_panel_kitchen_energy_produced")
            == "produced_energy"
        )

    def test_consumed_energy(self):
        """Recognize consumed energy sensor suffixes."""
        assert (
            _classify_sensor_role("span_panel_kitchen_energy_consumed")
            == "consumed_energy"
        )

    def test_net_energy(self):
        """Recognize net energy sensor suffixes."""
        assert _classify_sensor_role("span_panel_kitchen_energy_net") == "net_energy"

    def test_current(self):
        """Recognize circuit current sensor suffixes."""
        assert _classify_sensor_role("span_panel_kitchen_current") == "current"

    def test_breaker_rating(self):
        """Recognize breaker rating sensor suffixes."""
        assert (
            _classify_sensor_role("span_panel_kitchen_breaker_rating")
            == "breaker_rating"
        )

    def test_unrecognized(self):
        """Return None for unsupported sensor suffixes."""
        assert _classify_sensor_role("span_panel_kitchen_somethingElse") is None

    def test_empty_string(self):
        """Return None for empty unique ids."""
        assert _classify_sensor_role("") is None


class TestClassifySubDevice:
    """Tests for _classify_sub_device."""

    def test_bess(self):
        """Classify battery sub-devices from their identifiers."""
        device = MagicMock()
        device.identifiers = {(DOMAIN, "sp3-242424-001_bess")}
        assert _classify_sub_device(device) == "bess"

    def test_evse(self):
        """Classify EVSE sub-devices from their identifiers."""
        device = MagicMock()
        device.identifiers = {(DOMAIN, "sp3-242424-001_evse_0")}
        assert _classify_sub_device(device) == "evse"

    def test_unknown(self):
        """Treat the panel device itself as an unknown sub-device type."""
        device = MagicMock()
        device.identifiers = {(DOMAIN, "sp3-242424-001")}
        assert _classify_sub_device(device) == "unknown"


class TestFindConfigEntryId:
    """Tests for _find_config_entry_id."""

    def test_finds_span_entry(self):
        """Return the config entry id for SPAN panel devices."""
        device = MagicMock()
        device.identifiers = {(DOMAIN, "sp3-242424-001")}
        device.config_entries = {"entry_123"}
        assert _find_config_entry_id(device) == "entry_123"

    def test_non_span_device(self):
        """Ignore devices that do not belong to the SPAN domain."""
        device = MagicMock()
        device.identifiers = {("other_domain", "some_id")}
        device.config_entries = {"entry_123"}
        assert _find_config_entry_id(device) is None

    def test_no_config_entries(self):
        """Return None when a SPAN device has no linked config entries."""
        device = MagicMock()
        device.identifiers = {(DOMAIN, "sp3-242424-001")}
        device.config_entries = set()
        assert _find_config_entry_id(device) is None


class TestBuildCircuitEntityMap:
    """Tests for _build_circuit_entity_map."""

    def _make_entity(
        self, domain: str, unique_id: str | None, entity_id: str
    ) -> MagicMock:
        ent = MagicMock()
        ent.domain = domain
        ent.unique_id = unique_id
        ent.entity_id = entity_id
        return ent

    def test_skips_none_unique_id(self):
        """Skip entities whose unique_id is None."""
        entities = [
            self._make_entity("sensor", None, "sensor.orphan"),
        ]
        result = _build_circuit_entity_map({"circuit1"}, entities)
        assert result == {}

    def test_no_substring_collision(self):
        """Circuit id '1' must not match unique_id containing '15'."""
        entities = [
            self._make_entity("sensor", "panel_15_power", "sensor.circuit15_power"),
        ]
        result = _build_circuit_entity_map({"1"}, entities)
        assert "1" not in result

    def test_maps_power_sensor(self):
        """Map a circuit power sensor onto its circuit entry."""
        entities = [
            self._make_entity("sensor", "panel_circuit1_power", "sensor.kitchen_power"),
        ]
        result = _build_circuit_entity_map({"circuit1"}, entities)
        assert result["circuit1"]["power"] == "sensor.kitchen_power"

    def test_maps_switch_and_select(self):
        """Map switch and select entities onto the same circuit entry."""
        entities = [
            self._make_entity(
                "switch", "panel_circuit1_relay", "switch.kitchen_breaker"
            ),
            self._make_entity(
                "select", "panel_circuit1_priority", "select.kitchen_priority"
            ),
        ]
        result = _build_circuit_entity_map({"circuit1"}, entities)
        assert result["circuit1"]["switch"] == "switch.kitchen_breaker"
        assert result["circuit1"]["select"] == "select.kitchen_priority"

    def test_ignores_non_matching_entities(self):
        """Ignore entities that do not match the requested circuit ids."""
        entities = [
            self._make_entity(
                "sensor", "panel_circuit2_instantPowerW", "sensor.bedroom_power"
            ),
        ]
        result = _build_circuit_entity_map({"circuit1"}, entities)
        assert "circuit1" not in result

    def test_multiple_circuits(self):
        """Map entities for multiple circuits independently."""
        entities = [
            self._make_entity("sensor", "panel_c1_power", "sensor.c1_power"),
            self._make_entity("sensor", "panel_c2_power", "sensor.c2_power"),
        ]
        result = _build_circuit_entity_map({"c1", "c2"}, entities)
        assert result["c1"]["power"] == "sensor.c1_power"
        assert result["c2"]["power"] == "sensor.c2_power"

    def test_empty_entities(self):
        """Return an empty mapping when no entities are present."""
        result = _build_circuit_entity_map({"circuit1"}, [])
        assert result == {}

    def test_sensor_with_unknown_suffix_skipped(self):
        """Skip sensors whose suffix does not map to a supported role."""
        entities = [
            self._make_entity(
                "sensor", "panel_circuit1_unknownSuffix", "sensor.kitchen_unknown"
            ),
        ]
        result = _build_circuit_entity_map({"circuit1"}, entities)
        assert result.get("circuit1", {}) == {}

    def test_all_sensor_roles(self):
        """Map every supported circuit sensor role into the topology payload."""
        entities = [
            self._make_entity("sensor", "panel_c1_power", "sensor.c1_power"),
            self._make_entity(
                "sensor", "panel_c1_energy_produced", "sensor.c1_produced"
            ),
            self._make_entity(
                "sensor", "panel_c1_energy_consumed", "sensor.c1_consumed"
            ),
            self._make_entity("sensor", "panel_c1_energy_net", "sensor.c1_net"),
            self._make_entity("sensor", "panel_c1_current", "sensor.c1_current"),
            self._make_entity("sensor", "panel_c1_breaker_rating", "sensor.c1_breaker"),
        ]
        result = _build_circuit_entity_map({"c1"}, entities)
        assert len(result["c1"]) == 6


# ---------------------------------------------------------------------------
# Integration tests for handle_panel_topology
# ---------------------------------------------------------------------------


class TestHandlePanelTopology:
    """Tests for the panel_topology WebSocket command handler."""

    @pytest.mark.asyncio
    async def test_requires_admin(
        self,
        hass: HomeAssistant,
        hass_ws_client: WebSocketGenerator,
        hass_admin_user: MockUser,
    ) -> None:
        """Reject non-admin users before resolving topology data."""
        hass_admin_user.groups = []
        async_register_commands(hass)
        websocket_client = await hass_ws_client(hass)

        await websocket_client.send_json_auto_id(
            {"type": "span_panel/panel_topology", "device_id": "any-device-id"}
        )

        msg = await websocket_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_device_not_found(self, hass: HomeAssistant):
        """Error when device_id doesn't exist."""
        connection = _make_mock_connection()
        msg = {"id": 1, "type": "span_panel/panel_topology", "device_id": "nonexistent"}

        await _handle_panel_topology_inner(hass, connection, msg)

        connection.send_error.assert_called_once_with(
            1, "device_not_found", "Device not found"
        )

    @pytest.mark.asyncio
    async def test_non_span_device(self, hass: HomeAssistant):
        """Error when device exists but isn't a SPAN panel."""
        entry = MockConfigEntry(domain="other_domain", data={}, entry_id="other_entry")
        entry.add_to_hass(hass)

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id="other_entry",
            identifiers={("other_domain", "other_serial")},
        )

        connection = _make_mock_connection()
        msg = {"id": 1, "type": "span_panel/panel_topology", "device_id": device.id}

        await _handle_panel_topology_inner(hass, connection, msg)

        connection.send_error.assert_called_once_with(
            1, "not_span_panel", "Device is not a SPAN Panel device"
        )

    @pytest.mark.asyncio
    async def test_sub_device_id_rejected(self, hass: HomeAssistant):
        """Error when device_id is a BESS/EVSE sub-device, not the panel."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            entry_id="span_entry",
            unique_id="sp3-subdev-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(SpanPanelSnapshotFactory.create())
        )

        panel_device = _register_panel_device(
            hass, "span_entry", serial="sp3-subdev-001"
        )
        bess_device = _register_sub_device(
            hass,
            "span_entry",
            "sp3-subdev-001_bess",
            "SPAN Panel Battery",
            panel_device.id,
        )

        connection = _make_mock_connection()
        msg = {
            "id": 1,
            "type": "span_panel/panel_topology",
            "device_id": bess_device.id,
        }

        await _handle_panel_topology_inner(hass, connection, msg)

        connection.send_error.assert_called_once_with(
            1,
            "not_panel_device",
            "Use the SPAN panel device registry ID, not a BESS or EVSE sub-device.",
        )

    @pytest.mark.asyncio
    async def test_entry_not_loaded(self, hass: HomeAssistant):
        """Error when config entry exists but is not loaded."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            entry_id="span_entry",
            unique_id="sp3-242424-001",
        )
        entry.add_to_hass(hass)
        # State defaults to NOT_LOADED

        device = _register_panel_device(hass, "span_entry")

        connection = _make_mock_connection()
        msg = {"id": 1, "type": "span_panel/panel_topology", "device_id": device.id}

        await _handle_panel_topology_inner(hass, connection, msg)

        connection.send_error.assert_called_once_with(
            1, "not_loaded", "SPAN Panel integration is not loaded"
        )

    @pytest.mark.asyncio
    async def test_successful_topology_basic(self, hass: HomeAssistant):
        """Successful topology with basic circuits."""
        kitchen = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_kitchen",
            name="Kitchen",
            tabs=[5, 6],
            relay_state="CLOSED",
            is_user_controllable=True,
            breaker_rating_a=30,
        )
        bedroom = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_bedroom",
            name="Bedroom",
            tabs=[15],
            relay_state="CLOSED",
            is_user_controllable=True,
            breaker_rating_a=15,
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-test-001",
            firmware_version="spanos2/r202603/05",
            circuits={"uuid_kitchen": kitchen, "uuid_bedroom": bedroom},
            panel_size=32,
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={},
            entry_id="span_entry",
            unique_id="sp3-test-001",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        device = _register_panel_device(hass, "span_entry", serial="sp3-test-001")

        # Register a power sensor for the kitchen circuit.
        _register_entity(
            hass,
            "span_entry",
            device.id,
            "sensor",
            "span_panel_uuid_kitchen_power",
            "sensor.span_panel_kitchen_power",
            original_name="Kitchen Power",
        )

        connection = _make_mock_connection()
        msg = {"id": 1, "type": "span_panel/panel_topology", "device_id": device.id}

        await _handle_panel_topology_inner(hass, connection, msg)

        connection.send_error.assert_not_called()
        connection.send_result.assert_called_once()

        result = connection.send_result.call_args[0][1]

        assert result["serial"] == "sp3-test-001"
        assert result["firmware"] == "spanos2/r202603/05"
        assert result["panel_size"] == 32
        assert result["device_name"] == "SPAN Panel"

        # Kitchen circuit (240V).
        kitchen_data = result["circuits"]["uuid_kitchen"]
        assert kitchen_data["tabs"] == [5, 6]
        assert kitchen_data["name"] == "Kitchen"
        assert kitchen_data["voltage"] == 240
        assert kitchen_data["relay_state"] == "CLOSED"
        assert kitchen_data["breaker_rating_a"] == 30
        assert kitchen_data["entities"]["power"] == "sensor.span_panel_kitchen_power"

        # Bedroom circuit (120V).
        bedroom_data = result["circuits"]["uuid_bedroom"]
        assert bedroom_data["tabs"] == [15]
        assert bedroom_data["voltage"] == 120
        assert bedroom_data["entities"] == {}

    @pytest.mark.asyncio
    async def test_unmapped_circuits_excluded(self, hass: HomeAssistant):
        """Unmapped tab circuits are excluded from the topology."""
        circuit = SpanCircuitSnapshotFactory.create(circuit_id="uuid_real", name="Real")
        unmapped = SpanCircuitSnapshotFactory.create(
            circuit_id="unmapped_tab_5", name="Unmapped"
        )
        snapshot = SpanPanelSnapshotFactory.create(
            circuits={"uuid_real": circuit, "unmapped_tab_5": unmapped},
        )

        entry = MockConfigEntry(
            domain=DOMAIN, data={}, entry_id="span_entry", unique_id="sp3-242424-001"
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        device = _register_panel_device(hass, "span_entry")

        connection = _make_mock_connection()
        msg = {"id": 1, "type": "span_panel/panel_topology", "device_id": device.id}

        await _handle_panel_topology_inner(hass, connection, msg)

        result = connection.send_result.call_args[0][1]
        assert "uuid_real" in result["circuits"]
        assert "unmapped_tab_5" not in result["circuits"]

    @pytest.mark.asyncio
    async def test_sub_devices_included(self, hass: HomeAssistant):
        """BESS and EVSE sub-devices appear in the topology."""
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-sub-001",
            battery=SpanBatterySnapshotFactory.create(soe_percentage=85.0),
            evse={"evse-0": SpanEvseSnapshotFactory.create()},
        )

        entry = MockConfigEntry(
            domain=DOMAIN, data={}, entry_id="span_entry", unique_id="sp3-sub-001"
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        panel_device = _register_panel_device(hass, "span_entry", serial="sp3-sub-001")

        bess_device = _register_sub_device(
            hass,
            "span_entry",
            "sp3-sub-001_bess",
            "SPAN Panel Battery",
            panel_device.id,
        )
        evse_device = _register_sub_device(
            hass,
            "span_entry",
            "sp3-sub-001_evse_0",
            "SPAN Panel SPAN Drive",
            panel_device.id,
        )

        # Register an entity on the BESS device.
        _register_entity(
            hass,
            "span_entry",
            bess_device.id,
            "sensor",
            "sp3-sub-001_bess_battery_level",
            "sensor.span_panel_battery_level",
            original_name="Battery Level",
        )

        connection = _make_mock_connection()
        msg = {
            "id": 1,
            "type": "span_panel/panel_topology",
            "device_id": panel_device.id,
        }

        await _handle_panel_topology_inner(hass, connection, msg)

        result = connection.send_result.call_args[0][1]

        assert bess_device.id in result["sub_devices"]
        assert result["sub_devices"][bess_device.id]["type"] == "bess"
        assert result["sub_devices"][bess_device.id]["name"] == "SPAN Panel Battery"

        assert evse_device.id in result["sub_devices"]
        assert result["sub_devices"][evse_device.id]["type"] == "evse"

        # BESS entity should appear.
        bess_entities = result["sub_devices"][bess_device.id]["entities"]
        assert "sensor.span_panel_battery_level" in bess_entities

    @pytest.mark.asyncio
    async def test_evse_feed_circuit_entities_found(self, hass: HomeAssistant):
        """EVSE feed circuit sensor entities are found even though they live on the EVSE device."""
        evse_circuit = SpanCircuitSnapshotFactory.create(
            circuit_id="uuid_evse_feed",
            name="Garage",
            tabs=[30, 32],
            device_type="evse",
        )
        snapshot = SpanPanelSnapshotFactory.create(
            serial_number="sp3-evse-001",
            circuits={"uuid_evse_feed": evse_circuit},
            evse={
                "evse-0": SpanEvseSnapshotFactory.create(
                    feed_circuit_id="uuid_evse_feed"
                )
            },
        )

        entry = MockConfigEntry(
            domain=DOMAIN, data={}, entry_id="span_entry", unique_id="sp3-evse-001"
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.runtime_data = SpanPanelRuntimeData(
            coordinator=_make_coordinator(snapshot)
        )

        panel_device = _register_panel_device(hass, "span_entry", serial="sp3-evse-001")
        evse_device = _register_sub_device(
            hass,
            "span_entry",
            "sp3-evse-001_evse_0",
            "SPAN Drive",
            panel_device.id,
        )

        # Power sensor lives on the EVSE device, not the panel device.
        _register_entity(
            hass,
            "span_entry",
            evse_device.id,
            "sensor",
            "span_panel_uuid_evse_feed_power",
            "sensor.span_panel_garage_power",
        )

        connection = _make_mock_connection()
        msg = {
            "id": 1,
            "type": "span_panel/panel_topology",
            "device_id": panel_device.id,
        }

        await _handle_panel_topology_inner(hass, connection, msg)

        result = connection.send_result.call_args[0][1]
        circuit_data = result["circuits"]["uuid_evse_feed"]
        assert circuit_data["device_type"] == "evse"
        assert circuit_data["entities"]["power"] == "sensor.span_panel_garage_power"

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_registration(self, hass: HomeAssistant):
        """WebSocket commands can be registered without error."""
        async_register_commands(hass)
