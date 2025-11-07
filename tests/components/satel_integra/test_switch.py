"""Test Roborock Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import STATE_OFF, STATE_ON
from homeassistant.components.satel_integra.const import SIGNAL_OUTPUTS_UPDATED
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_CODE, MOCK_ENTRY_ID

from tests.common import MockConfigEntry, async_dispatcher_send, snapshot_platform


@pytest.fixture(autouse=True)
async def switches_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


async def add_mock_config_entry(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Add and fully set up a config entry, asserting it loads correctly."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.fixture
async def setup_mock_config_entry(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
):
    """Fixture to set up the config entry."""
    await add_mock_config_entry(hass, mock_config_entry_with_subentries)


@pytest.mark.usefixtures("mock_satel", "setup_mock_config_entry")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch correctly being set up."""
    await snapshot_platform(hass, entity_registry, snapshot, MOCK_ENTRY_ID)


async def test_switch_initial_state_on(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch has a correct initial state ON after initialization."""
    mock_satel.return_value.violated_outputs = [1]

    await add_mock_config_entry(hass, mock_config_entry_with_subentries)

    assert hass.states.get("switch.switchable_output").state == STATE_ON


@pytest.mark.usefixtures("mock_satel", "setup_mock_config_entry")
async def test_switch_callback(
    hass: HomeAssistant,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    # Should do nothing, only react to it's own number
    async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, {2: 1})

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, {1: 1})

    assert hass.states.get("switch.switchable_output").state == STATE_ON


@pytest.mark.usefixtures("mock_satel", "setup_mock_config_entry")
async def test_switch_change_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
) -> None:
    """Test switch correctly changes state after a callback from the panel."""
    controller = mock_satel.return_value
    controller.set_output = AsyncMock()

    assert hass.states.get("switch.switchable_output").state == STATE_OFF

    # Test turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.switchable_output"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.switchable_output").state == STATE_ON
    controller.set_output.assert_awaited_once_with(MOCK_CODE, 1, True)

    controller.set_output.reset_mock()

    # Test turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.switchable_output"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.switchable_output").state == STATE_OFF
    controller.set_output.assert_awaited_once_with(MOCK_CODE, 1, False)
