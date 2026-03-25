"""Tests for Span Panel circuit control functionality (switches, relay operations)."""

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from homeassistant.components.span_panel.switch import (
    _OPTIMISTIC_HOLD_SECONDS,
    SpanPanelCircuitsSwitch,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from .factories import SpanCircuitSnapshotFactory, SpanPanelSnapshotFactory


@pytest.fixture(autouse=True)
def expected_lingering_timers():
    """Fix expected lingering timers for tests."""
    return True


def _make_coordinator(
    circuits: dict[str, Any],
    *,
    panel_offline: bool = False,
    options: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a coordinator mock with a real snapshot from factories."""
    snapshot = SpanPanelSnapshotFactory.create(circuits=circuits)
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.panel_offline = panel_offline
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = options or {}
    coordinator.request_reload = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.client = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_switch_creation_for_controllable_circuit(hass: HomeAssistant) -> None:
    """Switches are created only for user-controllable circuits."""
    controllable = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        name="Kitchen Outlets",
        is_user_controllable=True,
    )
    non_controllable = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Main Feed",
        is_user_controllable=False,
    )
    coordinator = _make_coordinator({"1": controllable, "2": non_controllable})

    entities: list[Any] = []
    mock_entry = MagicMock()
    mock_entry.title = "SPAN Panel"
    mock_entry.data = {}
    mock_entry.runtime_data = MagicMock(coordinator=coordinator)

    await async_setup_entry(hass, mock_entry, lambda e, **kw: entities.extend(e))

    assert len(entities) == 1
    assert entities[0]._circuit_id == "1"


@pytest.mark.asyncio
async def test_switch_turn_on_operation() -> None:
    """Turning on a switch sends CLOSED to the client."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        name="Kitchen Outlets",
        relay_state="OPEN",
    )
    coordinator = _make_coordinator({"1": circuit})

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Kitchen Outlets", "SPAN Panel")
    await switch.async_turn_on()

    coordinator.client.set_circuit_relay.assert_called_once_with("1", "CLOSED")
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_switch_turn_off_operation() -> None:
    """Turning off a switch sends OPEN to the client."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        name="Kitchen Outlets",
        relay_state="CLOSED",
    )
    coordinator = _make_coordinator({"1": circuit})

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Kitchen Outlets", "SPAN Panel")
    await switch.async_turn_off()

    coordinator.client.set_circuit_relay.assert_called_once_with("1", "OPEN")
    coordinator.async_request_refresh.assert_called_once()


def test_switch_state_reflects_relay_state() -> None:
    """Switch is_on mirrors the circuit relay state."""
    closed = SpanCircuitSnapshotFactory.create(
        circuit_id="1", name="Kitchen", relay_state="CLOSED"
    )
    coordinator_closed = _make_coordinator({"1": closed})
    assert (
        SpanPanelCircuitsSwitch(coordinator_closed, "1", "Kitchen", "SPAN Panel").is_on
        is True
    )

    opened = SpanCircuitSnapshotFactory.create(
        circuit_id="1", name="Kitchen", relay_state="OPEN"
    )
    coordinator_open = _make_coordinator({"1": opened})
    assert (
        SpanPanelCircuitsSwitch(coordinator_open, "1", "Kitchen", "SPAN Panel").is_on
        is False
    )


def test_switch_handles_missing_circuit() -> None:
    """Constructing a switch for a missing circuit raises ValueError."""
    coordinator = _make_coordinator({})

    with pytest.raises(ValueError, match="Circuit 1 not found"):
        SpanPanelCircuitsSwitch(coordinator, "1", "Missing Circuit", "SPAN Panel")


def test_switch_coordinator_update_handling(hass: HomeAssistant) -> None:
    """Switch reflects new relay state after coordinator data changes."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        name="Kitchen Outlets",
        relay_state="CLOSED",
    )
    coordinator = _make_coordinator({"1": circuit})

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Kitchen Outlets", "SPAN Panel")
    switch.hass = hass
    switch.entity_id = "switch.span_panel_kitchen_outlets_breaker"
    switch.registry_entry = MagicMock()
    switch.platform = MagicMock(platform_name="switch")

    assert switch.is_on is True

    # Replace snapshot with an OPEN relay
    updated = replace(circuit, relay_state="OPEN")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"1": updated})
    switch._handle_coordinator_update()

    assert switch.is_on is False


def test_circuit_name_change_triggers_reload_request(hass: HomeAssistant) -> None:
    """Changing a circuit name triggers an integration reload."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        name="Kitchen Outlets",
        relay_state="CLOSED",
    )
    coordinator = _make_coordinator({"1": circuit})

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Kitchen Outlets", "SPAN Panel")
    switch.hass = hass
    switch.entity_id = "switch.span_panel_kitchen_outlets_breaker"
    switch.registry_entry = MagicMock()
    switch.platform = MagicMock(platform_name="switch")

    # Replace snapshot with a renamed circuit
    renamed = replace(circuit, name="New Kitchen Outlets")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"1": renamed})
    switch._handle_coordinator_update()

    coordinator.request_reload.assert_called_once()


def test_switch_unavailable_when_panel_offline() -> None:
    """Switches become unavailable when the panel is offline."""
    circuit = SpanCircuitSnapshotFactory.create(circuit_id="1")
    coordinator = _make_coordinator({"1": circuit}, panel_offline=True)

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")
    assert switch.available is False


def test_switch_extra_state_attributes_include_tabs_and_voltage() -> None:
    """Switches expose circuit tab and voltage metadata."""
    circuit = SpanCircuitSnapshotFactory.create(circuit_id="1", tabs=[1])
    coordinator = _make_coordinator({"1": circuit})

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")
    assert switch.extra_state_attributes == {"tabs": "tabs [1]", "voltage": 120}


@pytest.mark.asyncio
async def test_switch_turn_on_without_relay_support_logs_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Switches should no-op when the client lacks relay control."""
    circuit = SpanCircuitSnapshotFactory.create(circuit_id="1", relay_state="OPEN")
    coordinator = _make_coordinator({"1": circuit})
    coordinator.client = MagicMock(spec=[])

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")
    await switch.async_turn_on()

    assert "Client does not support relay control" in caplog.text
    coordinator.async_request_refresh.assert_not_called()


def test_switch_optimistic_hold_preserves_requested_state_until_timeout() -> None:
    """Coordinator updates should respect the optimistic hold window."""
    circuit = SpanCircuitSnapshotFactory.create(circuit_id="1", relay_state="OPEN")
    coordinator = _make_coordinator({"1": circuit})

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")
    switch._set_optimistic_state(True)

    # Panel still reports OPEN, but the optimistic hold should keep the switch on.
    switch._optimistic_set_at = 0.0
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "homeassistant.components.span_panel.switch.time.monotonic", lambda: 1.0
        )
        switch._update_is_on()
    assert switch.is_on is True

    # Once the hold window expires, the real panel state should win.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "homeassistant.components.span_panel.switch.time.monotonic",
            lambda: _OPTIMISTIC_HOLD_SECONDS + 1.0,
        )
        switch._update_is_on()
    assert switch.is_on is False


@pytest.mark.asyncio
async def test_switch_async_setup_entry_filters_supported_circuits(
    hass: HomeAssistant,
) -> None:
    """Setup should only create switches for supported controllable circuits."""
    controllable = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        is_user_controllable=True,
    )
    locked = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        is_user_controllable=False,
    )
    evse_upstream = replace(
        SpanCircuitSnapshotFactory.create(
            circuit_id="3",
            name="EV Upstream",
            is_user_controllable=True,
            tabs=[3, 4],
        ),
        device_type="evse",
        relative_position="UPSTREAM",
    )
    pv_downstream = replace(
        SpanCircuitSnapshotFactory.create(
            circuit_id="4",
            name="Solar",
            is_user_controllable=True,
            tabs=[5, 6],
        ),
        device_type="pv",
        relative_position="DOWNSTREAM",
    )

    coordinator = _make_coordinator(
        {
            "1": controllable,
            "2": locked,
            "3": evse_upstream,
            "4": pv_downstream,
        }
    )

    entities: list[Any] = []
    mock_entry = MagicMock()
    mock_entry.title = "SPAN Panel"
    mock_entry.data = {}
    mock_entry.runtime_data = MagicMock(coordinator=coordinator)

    await async_setup_entry(hass, mock_entry, lambda e, **kw: entities.extend(e))

    assert len(entities) == 2
    assert {entity._circuit_id for entity in entities} == {"1", "4"}


def test_switch_existing_entity_uses_solar_fallback_name(hass: HomeAssistant) -> None:
    """Existing solar switch entities should sync to the solar fallback label."""
    solar = replace(
        SpanCircuitSnapshotFactory.create(
            circuit_id="15",
            name="",
            tabs=[15],
            is_user_controllable=True,
        ),
        device_type="pv",
    )
    coordinator = _make_coordinator({"15": solar})
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = "switch.solar_breaker"
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "15", "", "SPAN Panel")

    assert switch.name == "Solar Breaker"


def test_switch_initial_install_uses_circuit_numbers_when_enabled(
    hass: HomeAssistant,
) -> None:
    """Initial switch names should honor the use-circuit-numbers option."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Kitchen",
        tabs=[2, 3],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"2": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "2", "Kitchen", "SPAN Panel")

    assert switch.name == "Circuit 2 3 Breaker"


def test_switch_initial_install_without_name_lets_ha_default(
    hass: HomeAssistant,
) -> None:
    """Unnamed switches on first install should let HA provide the name."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="3",
        name="",
        tabs=[3],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator({"3": circuit})
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "3", "", "SPAN Panel")

    assert switch._attr_name is None
    assert switch._previous_circuit_name is not None


def test_switch_first_update_requests_reload_without_user_override(
    hass: HomeAssistant,
) -> None:
    """First update should request a reload when no user override exists."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1", name="Kitchen", is_user_controllable=True
    )
    coordinator = _make_coordinator({"1": circuit})
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        init_registry = MagicMock()
        init_registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: init_registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "1", "Kitchen", "SPAN Panel")

    switch.hass = hass
    switch.entity_id = "switch.kitchen_breaker"
    switch.async_write_ha_state = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        runtime_registry = MagicMock()
        runtime_registry.async_get.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: runtime_registry,
        )
        switch._handle_coordinator_update()

    coordinator.request_reload.assert_called_once()


def test_switch_user_override_skips_reload_on_update(hass: HomeAssistant) -> None:
    """User-customized switch names should suppress auto-sync reloads."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1", name="Kitchen", is_user_controllable=True
    )
    coordinator = _make_coordinator({"1": circuit})
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        init_registry = MagicMock()
        init_registry.async_get_entity_id.return_value = "switch.kitchen_breaker"
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: init_registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "1", "Kitchen", "SPAN Panel")

    renamed = replace(circuit, name="Renamed Kitchen")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"1": renamed})
    switch.hass = hass
    switch.entity_id = "switch.kitchen_breaker"
    switch.async_write_ha_state = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        runtime_registry = MagicMock()
        runtime_registry.async_get.return_value = MagicMock(
            name="Custom Kitchen Breaker"
        )
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: runtime_registry,
        )
        switch._handle_coordinator_update()

    coordinator.request_reload.assert_not_called()
    assert switch._previous_circuit_name == "Renamed Kitchen"


def test_switch_update_is_on_clears_state_when_circuit_disappears(
    hass: HomeAssistant,
) -> None:
    """Switch state should clear when its circuit disappears from coordinator data."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1", is_user_controllable=True
    )
    coordinator = _make_coordinator({"1": circuit})
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")

    coordinator.data = SpanPanelSnapshotFactory.create(circuits={})
    switch._optimistic_state = True
    switch._update_is_on()

    assert switch.is_on is None
    assert switch._optimistic_state is None


@pytest.mark.asyncio
async def test_switch_turn_off_without_relay_support_logs_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Turning off should no-op when the client lacks relay control."""
    circuit = SpanCircuitSnapshotFactory.create(circuit_id="1", relay_state="CLOSED")
    coordinator = _make_coordinator({"1": circuit})
    coordinator.client = MagicMock(spec=[])

    switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")
    await switch.async_turn_off()

    assert "Client does not support relay control" in caplog.text
    coordinator.async_request_refresh.assert_not_called()


def test_switch_turn_on_off_schedule_async_tasks(hass: HomeAssistant) -> None:
    """Sync turn_on/turn_off wrappers should schedule async tasks."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1", is_user_controllable=True
    )
    coordinator = _make_coordinator({"1": circuit})
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")

    switch.hass = MagicMock()
    on_task = object()
    off_task = object()
    switch.async_turn_on = MagicMock(return_value=on_task)
    switch.async_turn_off = MagicMock(return_value=off_task)

    switch.turn_on()
    switch.turn_off()

    assert switch.hass.create_task.call_count == 2
    switch.hass.create_task.assert_any_call(on_task)
    switch.hass.create_task.assert_any_call(off_task)


def test_set_optimistic_state_writes_state_when_hass_present() -> None:
    """Setting optimistic state should immediately push HA state when attached."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1", is_user_controllable=True
    )
    coordinator = _make_coordinator({"1": circuit})
    coordinator.hass = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(coordinator, "1", "Test Circuit", "SPAN Panel")

    switch.hass = MagicMock()
    switch.async_write_ha_state = MagicMock()

    switch._set_optimistic_state(True)

    assert switch.is_on is True
    switch.async_write_ha_state.assert_called_once()


def test_switch_circuit_numbers_entity_id_stable_after_reload(
    hass: HomeAssistant,
) -> None:
    """Entity_id must stay circuit-based after name sync sets friendly display name."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"2": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    # --- Initial install: entity NOT in registry ---
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(
            coordinator, "2", "Air Conditioner", "SPAN Panel"
        )

    assert switch.name == "Circuit 15 17 Breaker"
    assert switch.entity_id == "switch.span_panel_circuit_15_17_breaker"

    # --- After reload: entity EXISTS in registry ---
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "switch.span_panel_circuit_15_17_breaker"
        )
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch2 = SpanPanelCircuitsSwitch(
            coordinator, "2", "Air Conditioner", "SPAN Panel"
        )

    # Entity_id must still be circuit-based
    assert switch2.name == "Circuit 15 17 Breaker"
    assert switch2.entity_id == "switch.span_panel_circuit_15_17_breaker"


def test_switch_circuit_numbers_entity_id_120v_single_tab(
    hass: HomeAssistant,
) -> None:
    """120V single-tab circuit should produce entity_id with one tab number."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="5",
        name="Kitchen Outlets",
        tabs=[10],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"5": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(
            coordinator, "5", "Kitchen Outlets", "SPAN Panel"
        )

    assert switch.name == "Circuit 10 Breaker"
    assert switch.entity_id == "switch.span_panel_circuit_10_breaker"


def test_switch_circuit_numbers_syncs_friendly_name_to_registry(
    hass: HomeAssistant,
) -> None:
    """Registry display name should be synced to the panel friendly name."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"2": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "switch.span_panel_circuit_15_17_breaker"
        )
        # Simulate registry entry with no user-set name.
        # Use PropertyMock because MagicMock(name=...) sets the mock's
        # internal label rather than the .name attribute.
        entity_entry = MagicMock()
        type(entity_entry).name = PropertyMock(return_value=None)
        registry.async_get.return_value = entity_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        SpanPanelCircuitsSwitch(coordinator, "2", "Air Conditioner", "SPAN Panel")

    registry.async_update_entity.assert_called_once_with(
        "switch.span_panel_circuit_15_17_breaker", name="Air Conditioner Breaker"
    )


def test_switch_circuit_numbers_preserves_user_custom_name(
    hass: HomeAssistant,
) -> None:
    """User-customized registry names must not be overwritten by sync."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"2": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "switch.span_panel_circuit_15_17_breaker"
        )
        # Simulate registry entry with a user-customized name.
        # Use PropertyMock because MagicMock(name=...) sets the mock's
        # internal label rather than the .name attribute.
        entity_entry = MagicMock()
        type(entity_entry).name = PropertyMock(return_value="My AC Unit")
        registry.async_get.return_value = entity_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        SpanPanelCircuitsSwitch(coordinator, "2", "Air Conditioner", "SPAN Panel")

    registry.async_update_entity.assert_not_called()


def test_switch_coordinator_update_circuit_numbers_updates_registry(
    hass: HomeAssistant,
) -> None:
    """In circuit-numbers mode, a name change should update the registry display name."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"2": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    # Create switch with entity already in registry (existing entity)
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "switch.span_panel_circuit_15_17_breaker"
        )
        entity_entry = MagicMock()
        type(entity_entry).name = PropertyMock(return_value="Air Conditioner Breaker")
        registry.async_get.return_value = entity_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(
            coordinator, "2", "Air Conditioner", "SPAN Panel"
        )

    # Simulate a circuit name change from "Air Conditioner" to "Kitchen AC"
    renamed = replace(circuit, name="Kitchen AC")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"2": renamed})
    switch.hass = hass
    switch.entity_id = "switch.span_panel_circuit_15_17_breaker"
    switch.async_write_ha_state = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        runtime_registry = MagicMock()
        runtime_entry = MagicMock()
        type(runtime_entry).name = PropertyMock(return_value="Air Conditioner Breaker")
        runtime_registry.async_get.return_value = runtime_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: runtime_registry,
        )
        switch._handle_coordinator_update()

    runtime_registry.async_update_entity.assert_called_once_with(
        "switch.span_panel_circuit_15_17_breaker", name="Kitchen AC Breaker"
    )
    coordinator.request_reload.assert_not_called()


def test_switch_coordinator_update_circuit_numbers_preserves_user_override(
    hass: HomeAssistant,
) -> None:
    """In circuit-numbers mode, user-customized registry names must not be overwritten."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="2",
        name="Air Conditioner",
        tabs=[15, 17],
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"2": circuit}, options={"use_circuit_numbers": True}
    )
    coordinator.hass = hass

    # Create switch with entity already in registry
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "switch.span_panel_circuit_15_17_breaker"
        )
        entity_entry = MagicMock()
        type(entity_entry).name = PropertyMock(return_value="Air Conditioner Breaker")
        registry.async_get.return_value = entity_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(
            coordinator, "2", "Air Conditioner", "SPAN Panel"
        )

    # Simulate a circuit name change; user has set "My AC Unit" in the registry
    renamed = replace(circuit, name="Kitchen AC")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"2": renamed})
    switch.hass = hass
    switch.entity_id = "switch.span_panel_circuit_15_17_breaker"
    switch.async_write_ha_state = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        runtime_registry = MagicMock()
        runtime_entry = MagicMock()
        type(runtime_entry).name = PropertyMock(return_value="My AC Unit")
        runtime_registry.async_get.return_value = runtime_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: runtime_registry,
        )
        switch._handle_coordinator_update()

    runtime_registry.async_update_entity.assert_not_called()
    coordinator.request_reload.assert_not_called()


def test_switch_coordinator_update_friendly_mode_still_reloads(
    hass: HomeAssistant,
) -> None:
    """In friendly-names mode, name changes should still trigger a reload."""
    circuit = SpanCircuitSnapshotFactory.create(
        circuit_id="1",
        name="Kitchen Outlets",
        is_user_controllable=True,
    )
    coordinator = _make_coordinator(
        {"1": circuit}, options={"use_circuit_numbers": False}
    )
    coordinator.hass = hass

    # Create switch with entity already in registry (previous name known)
    with pytest.MonkeyPatch.context() as mp:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = (
            "switch.span_panel_kitchen_outlets_breaker"
        )
        entity_entry = MagicMock()
        type(entity_entry).name = PropertyMock(return_value=None)
        registry.async_get.return_value = entity_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: registry,
        )
        switch = SpanPanelCircuitsSwitch(
            coordinator, "1", "Kitchen Outlets", "SPAN Panel"
        )

    assert switch._previous_circuit_name == "Kitchen Outlets"

    # Simulate a circuit name change
    renamed = replace(circuit, name="New Kitchen Outlets")
    coordinator.data = SpanPanelSnapshotFactory.create(circuits={"1": renamed})
    switch.hass = hass
    switch.entity_id = "switch.span_panel_kitchen_outlets_breaker"
    switch.async_write_ha_state = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        runtime_registry = MagicMock()
        runtime_entry = MagicMock()
        type(runtime_entry).name = PropertyMock(return_value=None)
        runtime_registry.async_get.return_value = runtime_entry
        mp.setattr(
            "homeassistant.components.span_panel.switch.er.async_get",
            lambda _hass: runtime_registry,
        )
        switch._handle_coordinator_update()

    coordinator.request_reload.assert_called_once()
