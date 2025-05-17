"""Test Redgtech switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.redgtech.switch import RedgtechSwitch
from homeassistant.components.redgtech.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_ON, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from redgtech_api.api import RedgtechConnectionError
from tests.common import MockConfigEntry


@pytest.fixture
def mock_device():
    """Return a mocked Redgtech device."""
    device = MagicMock()
    device.id = "1234-5678"
    device.name = "Test Switch"
    device.state = STATE_OFF
    return device


@pytest.fixture
def mock_coordinator(mock_device):
    """Return a mocked RedgtechDataUpdateCoordinator."""
    coordinator = AsyncMock()
    coordinator.data = [mock_device]
    coordinator.api = AsyncMock()
    coordinator.api.set_switch_state = AsyncMock()
    coordinator.access_token = "test_access_token"
    return coordinator


@pytest.fixture
def config_entry(mock_coordinator):
    """Return a mocked config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
        entry_id="test_entry",
    )
    entry.runtime_data = mock_coordinator
    return entry


@pytest.fixture
async def setup_switch(hass: HomeAssistant, config_entry, mock_coordinator, mock_device):
    """Set up the Redgtech switch for testing."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.redgtech.RedgtechDataUpdateCoordinator",
        return_value=mock_coordinator,
    ), patch("homeassistant.components.redgtech.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"switch.{mock_device.name.lower().replace(' ', '_')}"
    return entity_id


async def test_switch_initial_state(hass: HomeAssistant, setup_switch):
    """Test the initial state of the switch."""
    entity_id = setup_switch
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_turn_on_switch(hass: HomeAssistant, setup_switch, mock_coordinator, mock_device):
    """Test turning on the switch."""
    entity_id = setup_switch

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_coordinator.api.set_switch_state.assert_called_once_with(
        mock_device.id, True, mock_coordinator.access_token
    )
    mock_device.state = STATE_ON
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_turn_off_switch(hass: HomeAssistant, setup_switch, mock_coordinator, mock_device):
    """Test turning off the switch."""
    entity_id = setup_switch
    mock_device.state = STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    mock_coordinator.api.set_switch_state.assert_called_once_with(
        mock_device.id, False, mock_coordinator.access_token
    )
    mock_device.state = STATE_OFF
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_handle_connection_error(hass: HomeAssistant, setup_switch, mock_coordinator):
    """Test handling of connection errors when turning on the switch."""
    entity_id = setup_switch
    mock_coordinator.api.set_switch_state.side_effect = RedgtechConnectionError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
    mock_coordinator.api.set_switch_state.assert_called_once()