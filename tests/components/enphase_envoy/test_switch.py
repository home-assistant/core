"""Test Enphase Envoy switch."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.enphase_envoy import setup_with_selected_platforms


@pytest.mark.parametrize(
    ("mock_envoy", "entity_count"),
    [
        pytest.param("envoy_metered_batt_relay", 5, id="envoy_metered_batt_relay"),
    ],
    indirect=["mock_envoy"],
)
async def test_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy switch entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # these entities states should be created enabled from test data
    assert len(hass.states.async_all()) == entity_count
    assert entity_registry

    # compare registered entities against snapshot of prior run
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("mock_envoy", "entity_count"),
    [
        pytest.param("envoy", 0, id="envoy"),
    ],
    indirect=["mock_envoy"],
)
async def test_no_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy switch entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # these entities states should be created enabled from test data
    assert len(hass.states.async_all()) == entity_count


@pytest.mark.parametrize(
    ("mock_envoy", "entity_id", "initial_value"),
    [
        pytest.param(
            "envoy_metered_batt_relay",
            "switch.enpower_654321_grid_enabled",
            STATE_ON,
            id="envoy_metered_batt_relay",
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_switch_grid_operation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
    mock_close_dry_contact: AsyncMock,
    mock_open_dry_contact: AsyncMock,
    mock_disable_charge_from_grid: AsyncMock,
    mock_enable_charge_from_grid: AsyncMock,
    entity_id: str,
    initial_value: str,
) -> None:
    """Test enphase_envoy switch entities operation."""

    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    # test each option for relays
    for option in INITIAL_OFF_ORDER if initial_value == STATE_OFF else INITIAL_ON_ORDER:
        await hass.services.async_call(
            Platform.SWITCH,
            option,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert mock_go_on_grid.await_count == (2 if initial_value == STATE_OFF else 1)
    assert mock_go_off_grid.await_count == (2 if initial_value == STATE_ON else 1)

    # these should not been awaited
    mock_close_dry_contact.assert_not_called()
    mock_open_dry_contact.assert_not_called()
    mock_enable_charge_from_grid.assert_not_called()
    mock_disable_charge_from_grid.assert_not_called()


@pytest.mark.parametrize(
    ("mock_envoy", "entity_id", "initial_value"),
    [
        pytest.param(
            "envoy_metered_batt_relay",
            "switch.enpower_654321_charge_from_grid",
            STATE_ON,
            id="envoy_metered_batt_relay",
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_switch_grid_charge(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
    mock_close_dry_contact: AsyncMock,
    mock_open_dry_contact: AsyncMock,
    mock_disable_charge_from_grid: AsyncMock,
    mock_enable_charge_from_grid: AsyncMock,
    entity_id: str,
    initial_value: str,
) -> None:
    """Test enphase_envoy switch entities operation."""

    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    # test each option for relays
    for option in INITIAL_OFF_ORDER if initial_value == STATE_OFF else INITIAL_ON_ORDER:
        await hass.services.async_call(
            Platform.SWITCH,
            option,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert mock_enable_charge_from_grid.await_count == (
        2 if initial_value == STATE_OFF else 1
    )
    assert mock_disable_charge_from_grid.await_count == (
        2 if initial_value == STATE_ON else 1
    )

    # these should not been awaited
    mock_close_dry_contact.assert_not_called()
    mock_open_dry_contact.assert_not_called()
    mock_go_on_grid.assert_not_called()
    mock_go_off_grid.assert_not_called()


@pytest.mark.parametrize(
    ("mock_envoy", "entity_id", "initial_value"),
    [
        pytest.param(
            "envoy_metered_batt_relay",
            "switch.nc1_fixture",
            STATE_OFF,
            id="envoy_metered_batt_relay",
        ),
        pytest.param(
            "envoy_metered_batt_relay",
            "switch.nc2_fixture",
            STATE_ON,
            id="envoy_metered_batt_relay",
        ),
        pytest.param(
            "envoy_metered_batt_relay",
            "switch.nc3_fixture",
            STATE_OFF,
            id="envoy_metered_batt_relay",
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_switch_relay_operation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
    mock_close_dry_contact: AsyncMock,
    mock_open_dry_contact: AsyncMock,
    mock_disable_charge_from_grid: AsyncMock,
    mock_enable_charge_from_grid: AsyncMock,
    entity_id: str,
    initial_value: str,
) -> None:
    """Test enphase_envoy switch entities operation."""

    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    # test each option for relays
    for option in INITIAL_OFF_ORDER if initial_value == STATE_OFF else INITIAL_ON_ORDER:
        await hass.services.async_call(
            Platform.SWITCH,
            option,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert mock_close_dry_contact.await_count == (
        2 if initial_value == STATE_OFF else 1
    )
    assert mock_open_dry_contact.await_count == (2 if initial_value == STATE_ON else 1)

    # these should not been awaited
    mock_go_off_grid.assert_not_called()
    mock_go_on_grid.assert_not_called()
    mock_enable_charge_from_grid.assert_not_called()
    mock_disable_charge_from_grid.assert_not_called()
