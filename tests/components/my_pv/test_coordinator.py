"""Test the my-PV coordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from my_pv.exceptions import MyPVTooManyRequestsError
import pytest

from homeassistant.components.my_pv.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_coordinator_update_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a coordinator update."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Test successful setup and first data fetch
    await hass.async_block_till_done()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]

    # Test successful data fetch
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]


async def test_coordinator_update_data_not_connected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator update when client not connected."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Test successful setup and first data fetch
    await hass.async_block_till_done()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]

    # Test states get unavailable when not connected
    freezer.tick(UPDATE_INTERVAL)
    mock_my_pv_client.connected = False
    mock_my_pv_client.connect = AsyncMock(return_value=False)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_my_pv_client.connect.assert_awaited_once_with()
    states = hass.states.async_all()
    assert False not in [state.state == STATE_UNAVAILABLE for state in states]

    # Test successful data fetch
    freezer.tick(UPDATE_INTERVAL)
    mock_my_pv_client.connected = False
    mock_my_pv_client.connect.reset_mock()

    async def reconnect() -> bool:
        mock_my_pv_client.connected = True
        return True

    mock_my_pv_client.connect.side_effect = reconnect

    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_my_pv_client.connect.assert_awaited_once_with()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]


async def test_coordinator_update_data_rate_limiting(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator update when client is rate limiting."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Test successful setup and first data fetch
    await hass.async_block_till_done()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]

    # Test states stay available when rate limiting
    freezer.tick(UPDATE_INTERVAL)
    mock_my_pv_client.fetch_data = AsyncMock(side_effect=MyPVTooManyRequestsError)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_my_pv_client.fetch_data.assert_awaited_once_with()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]

    # Test successful data fetch
    freezer.tick(2 * UPDATE_INTERVAL)
    mock_my_pv_client.fetch_data.reset_mock(side_effect=True)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_my_pv_client.fetch_data.assert_awaited_once_with()
    states = hass.states.async_all()
    assert False not in [state.state != STATE_UNAVAILABLE for state in states]
