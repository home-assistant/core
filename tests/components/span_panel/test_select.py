"""Tests for select entity functionality."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from span_panel_api.exceptions import SpanPanelServerError

from homeassistant.components.span_panel.const import CircuitPriority
from homeassistant.components.span_panel.select import (
    CIRCUIT_PRIORITY_DESCRIPTION,
    SpanPanelCircuitsSelect,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from .factories import SpanCircuitSnapshotFactory, SpanPanelSnapshotFactory


def _make_coordinator_with_circuit(
    circuit_id: str = "id",
    circuit_name: str = "name",
    priority: str = "SOC_THRESHOLD",
) -> MagicMock:
    """Build a mock coordinator whose .data contains a single circuit."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id=circuit_id,
        name=circuit_name,
        relay_state="CLOSED",
        instant_power_w=100.0,
        produced_energy_wh=0.0,
        consumed_energy_wh=50.0,
        tabs=[1],
        priority=priority,
        is_user_controllable=True,
    )

    snapshot = SpanPanelSnapshotFactory.create(
        circuits={circuit_id: circuit},
    )

    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}
    return coordinator


def test_select_init_missing_circuit() -> None:
    """Test that initializing with a missing circuit_id raises ValueError."""
    # Coordinator with no circuits
    snapshot = SpanPanelSnapshotFactory.create(circuits={})
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}

    with pytest.raises(ValueError):
        SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "bad_id", "name", "Test Device"
        )


@pytest.mark.asyncio
async def test_async_select_option_service_not_found() -> None:
    """Test that ServiceNotFound triggers a notification."""
    coordinator = _make_coordinator_with_circuit()
    circuit = coordinator.data.circuits["id"]

    with patch(
        "homeassistant.components.span_panel.select.async_create_span_notification",
        new_callable=AsyncMock,
    ) as mock_notification:
        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "name", "Test Device"
        )
        select.coordinator = coordinator
        select.hass = MagicMock()

        # Make the client's set_circuit_priority raise ServiceNotFound
        coordinator.client = AsyncMock()
        coordinator.client.set_circuit_priority = AsyncMock(
            side_effect=ServiceNotFound("test_domain", "test_service")
        )

        select._get_circuit = MagicMock(return_value=circuit)
        await select.async_select_option(CircuitPriority.SOC_THRESHOLD.value)

        mock_notification.assert_called_once()


@pytest.mark.asyncio
async def test_async_select_option_server_error() -> None:
    """Test that SpanPanelServerError triggers a notification."""
    coordinator = _make_coordinator_with_circuit()
    circuit = coordinator.data.circuits["id"]

    with patch(
        "homeassistant.components.span_panel.select.async_create_span_notification",
        new_callable=AsyncMock,
    ) as mock_notification:
        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "name", "Test Device"
        )
        select.coordinator = coordinator
        select.hass = MagicMock()

        coordinator.client = AsyncMock()
        coordinator.client.set_circuit_priority = AsyncMock(
            side_effect=SpanPanelServerError("test error")
        )

        select._get_circuit = MagicMock(return_value=circuit)
        await select.async_select_option(CircuitPriority.SOC_THRESHOLD.value)

        mock_notification.assert_called_once()


@pytest.mark.asyncio
async def test_async_select_option_success_refreshes_coordinator() -> None:
    """Successful priority changes should refresh coordinator data."""
    coordinator = _make_coordinator_with_circuit()
    coordinator.hass = MagicMock()
    coordinator.async_request_refresh = AsyncMock()

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mock_async_get.return_value = registry
        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )

    coordinator.client = MagicMock()
    coordinator.client.set_circuit_priority = AsyncMock()
    select.hass = MagicMock()

    await select.async_select_option(CircuitPriority.SOC_THRESHOLD.value)

    coordinator.client.set_circuit_priority.assert_awaited_once_with(
        "id", "SOC_THRESHOLD"
    )
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_select_option_without_priority_support_returns_early(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Clients without priority support should log and return without refresh."""
    coordinator = _make_coordinator_with_circuit()
    coordinator.hass = MagicMock()
    coordinator.async_request_refresh = AsyncMock()

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mock_async_get.return_value = registry
        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )

    coordinator.client = object()
    select.hass = MagicMock()
    caplog.set_level("WARNING")

    await select.async_select_option(CircuitPriority.SOC_THRESHOLD.value)

    assert "Client does not support priority control" in caplog.text
    coordinator.async_request_refresh.assert_not_awaited()


def test_select_uses_circuit_number_name_when_option_enabled() -> None:
    """Number-based naming should use breaker tabs when configured."""
    coordinator = _make_coordinator_with_circuit()
    coordinator.config_entry.options = {"use_circuit_numbers": True}
    coordinator.hass = MagicMock()

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )

    assert select.name == "Circuit 1 Circuit Priority"


def test_select_unnamed_friendly_mode_leaves_name_none() -> None:
    """Unnamed selects in friendly-name mode should defer to HA naming."""
    coordinator = _make_coordinator_with_circuit(circuit_name="")
    coordinator.hass = MagicMock()

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "", "SPAN Panel"
        )

    assert select.name is None


def test_select_existing_entity_uses_solar_fallback_name() -> None:
    """Existing unnamed PV entities should use the solar fallback name."""
    circuit = replace(
        SpanCircuitSnapshotFactory.create(
            circuit_id="pv-1",
            name=None,
            tabs=[9, 10],
            priority="SOC_THRESHOLD",
        ),
        device_type="pv",
    )
    snapshot = SpanPanelSnapshotFactory.create(circuits={"pv-1": circuit})
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.hass = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = "select.solar_circuit_priority"
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "pv-1", "", "SPAN Panel"
        )

    assert select.name == "Solar Circuit Priority"


def test_select_available_false_when_panel_offline() -> None:
    """Select entities become unavailable when the panel is offline."""
    coordinator = _make_coordinator_with_circuit()
    coordinator.panel_offline = True

    select = SpanPanelCircuitsSelect(
        coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
    )

    assert select.available is False


def test_select_extra_state_attributes_include_tabs_and_voltage() -> None:
    """Select attributes should expose breaker tabs and circuit voltage."""
    coordinator = _make_coordinator_with_circuit()
    coordinator.hass = MagicMock()
    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )

    assert select.extra_state_attributes == {"tabs": "tabs [1]", "voltage": 120}


def test_handle_coordinator_update_requests_reload_on_first_sync() -> None:
    """First update for an entity not yet in the registry should request reload."""
    coordinator = _make_coordinator_with_circuit(circuit_name="Kitchen")
    coordinator.hass = MagicMock()
    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        registry.async_get.return_value = None
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )
        select.hass = MagicMock()
        select.async_write_ha_state = MagicMock()
        select.entity_id = "select.kitchen_circuit_priority"

        select._handle_coordinator_update()

    coordinator.request_reload.assert_called_once()


def test_handle_coordinator_update_user_override_skips_reload() -> None:
    """Customized select names should suppress automatic name sync reloads."""
    coordinator = _make_coordinator_with_circuit(circuit_name="Kitchen")
    coordinator.hass = MagicMock()
    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = "select.kitchen_circuit_priority"
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )

    updated_circuit = replace(coordinator.data.circuits["id"], name="Renamed Kitchen")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"id": updated_circuit})
    select.hass = MagicMock()
    select.async_write_ha_state = MagicMock()
    select.entity_id = "select.kitchen_circuit_priority"

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        runtime_registry = MagicMock()
        runtime_registry.async_get.return_value = MagicMock(
            name="Custom Kitchen Priority"
        )
        mock_async_get.return_value = runtime_registry
        select._handle_coordinator_update()

    coordinator.request_reload.assert_not_called()
    assert select._previous_circuit_name == "Renamed Kitchen"


def test_handle_coordinator_update_requests_reload_on_name_change() -> None:
    """Later circuit renames should request a select reload."""
    coordinator = _make_coordinator_with_circuit(circuit_name="Kitchen")
    coordinator.hass = MagicMock()
    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = "select.kitchen_circuit_priority"
        mock_async_get.return_value = registry

        select = SpanPanelCircuitsSelect(
            coordinator, CIRCUIT_PRIORITY_DESCRIPTION, "id", "Kitchen", "SPAN Panel"
        )

    updated_circuit = replace(coordinator.data.circuits["id"], name="Renamed Kitchen")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"id": updated_circuit})
    select.hass = MagicMock()
    select.async_write_ha_state = MagicMock()
    select.entity_id = "select.kitchen_circuit_priority"

    with patch(
        "homeassistant.components.span_panel.select.er.async_get"
    ) as mock_async_get:
        runtime_registry = MagicMock()
        runtime_registry.async_get.return_value = None
        mock_async_get.return_value = runtime_registry
        select._handle_coordinator_update()

    coordinator.request_reload.assert_called_once()
    assert select._previous_circuit_name == "Renamed Kitchen"


@pytest.mark.asyncio
async def test_async_setup_entry_filters_supported_circuits() -> None:
    """Platform setup should only create selects for supported controllable circuits."""
    controllable = SpanCircuitSnapshotFactory.create(
        circuit_id="main-1",
        name="Kitchen",
        is_user_controllable=True,
        tabs=[1],
    )
    not_controllable = SpanCircuitSnapshotFactory.create(
        circuit_id="main-2",
        name="Locked",
        is_user_controllable=False,
        tabs=[2],
    )
    evse_upstream = replace(
        SpanCircuitSnapshotFactory.create(
            circuit_id="evse-1",
            name="EV Upstream",
            is_user_controllable=True,
            tabs=[3, 4],
        ),
        device_type="evse",
        relative_position="UPSTREAM",
    )
    pv_downstream = replace(
        SpanCircuitSnapshotFactory.create(
            circuit_id="pv-1",
            name="Solar",
            is_user_controllable=True,
            tabs=[5, 6],
        ),
        device_type="pv",
        relative_position="DOWNSTREAM",
    )

    coordinator = MagicMock()
    coordinator.data = SpanPanelSnapshotFactory.create(
        circuits={
            "main-1": controllable,
            "main-2": not_controllable,
            "evse-1": evse_upstream,
            "pv-1": pv_downstream,
        }
    )
    config_entry = MagicMock()
    config_entry.title = "SPAN Panel"
    config_entry.data = {}
    config_entry.runtime_data = MagicMock(coordinator=coordinator)
    async_add_entities = MagicMock()

    await async_setup_entry(MagicMock(), config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 2
    assert {entity.id for entity in entities} == {"main-1", "pv-1"}


def test_select_circuit_numbers_entity_id_stable_after_reload(
    hass: HomeAssistant,
) -> None:
    """Entity_id must stay circuit-based after name sync sets friendly display name."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    snapshot = SpanPanelSnapshotFactory.create(circuits={"2": circuit})
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {"use_circuit_numbers": True}
    coordinator.hass = hass

    # --- Initial install: entity NOT in registry ---
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.select.er.async_get",
            lambda _hass: registry,
        )
        select = SpanPanelCircuitsSelect(
            coordinator,
            CIRCUIT_PRIORITY_DESCRIPTION,
            "2",
            "Air Conditioner",
            "SPAN Panel",
        )

    assert select.name == "Circuit 15 17 Circuit Priority"
    assert select.entity_id == "select.span_panel_circuit_15_17_circuit_priority"

    # --- After reload: entity EXISTS in registry ---
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "select.span_panel_circuit_15_17_circuit_priority"
        )
        mp.setattr(
            "homeassistant.components.span_panel.select.er.async_get",
            lambda _hass: registry,
        )
        select2 = SpanPanelCircuitsSelect(
            coordinator,
            CIRCUIT_PRIORITY_DESCRIPTION,
            "2",
            "Air Conditioner",
            "SPAN Panel",
        )

    # Entity_id must still be circuit-based
    assert select2.name == "Circuit 15 17 Circuit Priority"
    assert select2.entity_id == "select.span_panel_circuit_15_17_circuit_priority"


def test_select_circuit_numbers_entity_id_120v_single_tab(
    hass: HomeAssistant,
) -> None:
    """120V single-tab circuit should produce entity_id with one tab number."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="5",
        name="Kitchen Outlets",
        tabs=[10],
        is_user_controllable=True,
    )
    snapshot = SpanPanelSnapshotFactory.create(circuits={"5": circuit})
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {"use_circuit_numbers": True}
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.select.er.async_get",
            lambda _hass: registry,
        )
        select = SpanPanelCircuitsSelect(
            coordinator,
            CIRCUIT_PRIORITY_DESCRIPTION,
            "5",
            "Kitchen Outlets",
            "SPAN Panel",
        )

    assert select.name == "Circuit 10 Circuit Priority"
    assert select.entity_id == "select.span_panel_circuit_10_circuit_priority"


def test_select_coordinator_update_circuit_numbers_updates_registry(
    hass: HomeAssistant,
) -> None:
    """In circuit-numbers mode, a name change should update the registry display name."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    snapshot = SpanPanelSnapshotFactory.create(circuits={"2": circuit})
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {"use_circuit_numbers": True}
    coordinator.hass = hass

    # Create select with entity already in registry (existing entity)
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "select.span_panel_circuit_15_17_circuit_priority"
        )
        entity_entry = MagicMock()
        type(entity_entry).name = PropertyMock(
            return_value="Air Conditioner Circuit Priority"
        )
        registry.async_get.return_value = entity_entry
        mp.setattr(
            "homeassistant.components.span_panel.select.er.async_get",
            lambda _hass: registry,
        )
        select = SpanPanelCircuitsSelect(
            coordinator,
            CIRCUIT_PRIORITY_DESCRIPTION,
            "2",
            "Air Conditioner",
            "SPAN Panel",
        )

    # Simulate a circuit name change from "Air Conditioner" to "Kitchen AC"
    renamed = replace(circuit, name="Kitchen AC")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"2": renamed})
    select.hass = hass
    select.entity_id = "select.span_panel_circuit_15_17_circuit_priority"
    select.async_write_ha_state = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        runtime_registry = MagicMock()
        runtime_entry = MagicMock()
        type(runtime_entry).name = PropertyMock(
            return_value="Air Conditioner Circuit Priority"
        )
        runtime_registry.async_get.return_value = runtime_entry
        mp.setattr(
            "homeassistant.components.span_panel.select.er.async_get",
            lambda _hass: runtime_registry,
        )
        select._handle_coordinator_update()

    runtime_registry.async_update_entity.assert_called_once_with(
        "select.span_panel_circuit_15_17_circuit_priority",
        name="Kitchen AC Circuit Priority",
    )
    coordinator.request_reload.assert_not_called()
