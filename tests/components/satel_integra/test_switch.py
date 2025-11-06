"""Test Roborock Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import STATE_OFF, STATE_ON
from homeassistant.components.satel_integra.const import SIGNAL_OUTPUTS_UPDATED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_CODE

from tests.common import MockConfigEntry, async_dispatcher_send, snapshot_platform
from tests.components.switch import common


@pytest.fixture(autouse=True)
async def switches_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


async def test_switches(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch correctly being set up."""

    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_subentries.entry_id
    )


async def test_switch_initial_state_off(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch has a correct initial state OFF after initialization."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("switch.switchable_output").state == STATE_OFF


async def test_switch_initial_state_on(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch has a correct initial state ON after initialization."""
    mock_satel.return_value.violated_outputs = [1]

    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("switch.switchable_output").state == STATE_ON


async def test_switch_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    # Should do nothing, only react to it's own number
    async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, {2: 1})

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, {1: 1})

    assert hass.states.get("switch.switchable_output").state == STATE_ON


async def test_switch_change_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    controller = mock_satel.return_value
    controller.set_output = AsyncMock()

    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    # Test turn on
    await common.async_turn_on(hass, "switch.switchable_output")
    assert hass.states.get("switch.switchable_output").state == STATE_ON
    controller.set_output.assert_awaited_once_with(MOCK_CODE, 1, True)

    controller.set_output.reset_mock()

    # Test turn on
    await common.async_turn_off(hass, "switch.switchable_output")
    assert hass.states.get("switch.switchable_output").state == STATE_OFF
    controller.set_output.assert_awaited_once_with(MOCK_CODE, 1, False)
