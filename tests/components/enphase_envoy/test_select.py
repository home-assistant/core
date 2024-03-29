"""Test Enphase Envoy diagnostics."""

from unittest.mock import AsyncMock

from pyenphase.models.dry_contacts import DryContactAction, DryContactMode
from pyenphase.models.tariff import EnvoyStorageMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.select import (
    ACTION_OPTIONS,
    MODE_OPTIONS,
    RELAY_ACTION_MAP,
    RELAY_MODE_MAP,
    REVERSE_RELAY_ACTION_MAP,
    REVERSE_RELAY_MODE_MAP,
    REVERSE_STORAGE_MODE_MAP,
    STORAGE_MODE_MAP,
    STORAGE_MODE_OPTIONS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.enphase_envoy import setup_with_selected_platforms


async def test_select(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
) -> None:
    """Test enphase_envoy select entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SELECT])

    # these entities states should be created from test data
    assert len(hass.states.async_all()) == 13

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
    ("entity_id", "relay_id", "expected_action", "initial_value"),
    [
        (
            "select.grid_action",
            "NC1",
            "grid_action",
            RELAY_ACTION_MAP[DryContactAction.SHED],
        ),
        (
            "select.grid_action_2",
            "NC2",
            "grid_action",
            RELAY_ACTION_MAP[DryContactAction.APPLY],
        ),
        (
            "select.grid_action_3",
            "NC3",
            "grid_action",
            RELAY_ACTION_MAP[DryContactAction.APPLY],
        ),
        (
            "select.microgrid_action",
            "NC1",
            "micro_grid_action",
            RELAY_ACTION_MAP[DryContactAction.SCHEDULE],
        ),
        (
            "select.microgrid_action_2",
            "NC2",
            "micro_grid_action",
            RELAY_ACTION_MAP[DryContactAction.NONE],
        ),
        (
            "select.microgrid_action_3",
            "NC3",
            "micro_grid_action",
            RELAY_ACTION_MAP[DryContactAction.SHED],
        ),
        (
            "select.generator_action",
            "NC1",
            "generator_action",
            RELAY_ACTION_MAP[DryContactAction.APPLY],
        ),
        (
            "select.generator_action_2",
            "NC2",
            "generator_action",
            RELAY_ACTION_MAP[DryContactAction.SHED],
        ),
        (
            "select.generator_action_3",
            "NC3",
            "generator_action",
            RELAY_ACTION_MAP[DryContactAction.NONE],
        ),
    ],
)
async def test_select_relay_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_update_dry_contact: AsyncMock,
    entity_id: str,
    relay_id: str,
    expected_action: str,
    initial_value: str,
) -> None:
    """Test enphase_envoy select relay entities actions."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SELECT])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    # test each action for relays
    for action in ACTION_OPTIONS:
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {
                ATTR_ENTITY_ID: entity_id,
                "option": action,
            },
            blocking=True,
        )
        mock_update_dry_contact.assert_awaited_once()
        mock_update_dry_contact.assert_called_with(
            {"id": relay_id, expected_action: REVERSE_RELAY_ACTION_MAP[action]}
        )
        mock_update_dry_contact.reset_mock()


@pytest.mark.parametrize(
    ("entity_id", "relay_id", "expected_mode", "initial_value"),
    [
        (
            "select.envoy_1234_mode",
            "NC1",
            "mode",
            RELAY_MODE_MAP[DryContactMode.STATE_OF_CHARGE],
        ),
        (
            "select.envoy_1234_mode_2",
            "NC2",
            "mode",
            RELAY_MODE_MAP[DryContactMode.MANUAL],
        ),
        (
            "select.envoy_1234_mode_3",
            "NC3",
            "mode",
            RELAY_MODE_MAP[DryContactMode.MANUAL],
        ),
    ],
)
async def test_select_relay_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_update_dry_contact: AsyncMock,
    entity_id: str,
    relay_id: str,
    expected_mode: str,
    initial_value: str,
) -> None:
    """Test enphase_envoy select relay entities modes."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SELECT])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    # test each mode for relays
    for mode in MODE_OPTIONS:
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {
                ATTR_ENTITY_ID: entity_id,
                "option": mode,
            },
            blocking=True,
        )
        mock_update_dry_contact.assert_awaited_once()
        mock_update_dry_contact.assert_called_with(
            {"id": relay_id, expected_mode: REVERSE_RELAY_MODE_MAP[mode]}
        )
        mock_update_dry_contact.reset_mock()


@pytest.mark.parametrize(
    ("entity_id", "initial_value"),
    [
        (
            "select.enpower_654321_storage_mode",
            STORAGE_MODE_MAP[EnvoyStorageMode.SELF_CONSUMPTION],
        ),
    ],
)
async def test_select_storage_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_set_storage_mode: AsyncMock,
    entity_id: str,
    initial_value: str,
) -> None:
    """Test enphase_envoy select entities storage modes."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SELECT])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    # test each mode for relays
    for mode in STORAGE_MODE_OPTIONS:
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {
                ATTR_ENTITY_ID: entity_id,
                "option": mode,
            },
            blocking=True,
        )
        mock_set_storage_mode.assert_awaited_once()
        mock_set_storage_mode.assert_called_with(REVERSE_STORAGE_MODE_MAP[mode])
        mock_set_storage_mode.reset_mock()
