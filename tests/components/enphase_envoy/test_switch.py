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
from tests.components.enphase_envoy import (
    setup_with_selected_platforms,
    validate_entity_count,
)


async def test_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    test_parameters,
) -> None:
    """Test enphase_envoy switch entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # these entities states should be created enabled from test data
    assert await validate_entity_count(hass, test_parameters, Platform.SWITCH)

    entity_registry = er.async_get(hass)
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
    ("entity_id", "initial_value"),
    [
        ("switch.enpower_654321_grid_enabled", STATE_ON),
    ],
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
    ("entity_id", "initial_value"),
    [
        ("switch.enpower_654321_charge_from_grid", STATE_ON),
    ],
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
    ("entity_id", "initial_value"),
    [
        ("switch.nc1_fixture", STATE_OFF),
        ("switch.nc2_fixture", STATE_ON),
        ("switch.nc3_fixture", STATE_OFF),
    ],
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
