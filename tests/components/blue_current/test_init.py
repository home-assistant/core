"""Test Blue Current Init Component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from bluecurrent_api.client import Client
from bluecurrent_api.exceptions import (
    BlueCurrentException,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)
import pytest

from homeassistant.components.blue_current import DOMAIN, Connector, async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    IntegrationError,
)
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test load and unload entry."""
    with patch("homeassistant.components.blue_current.Client", autospec=True):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("api_error", "config_error"),
    [
        (InvalidApiToken, ConfigEntryAuthFailed),
        (BlueCurrentException, ConfigEntryNotReady),
    ],
)
async def test_config_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_error: BlueCurrentException,
    config_error: IntegrationError,
) -> None:
    """Test if the correct config error is raised when connecting to the api fails."""
    with patch(
        "homeassistant.components.blue_current.Client.connect",
        side_effect=api_error,
    ), pytest.raises(config_error):
        config_entry.add_to_hass(hass)
        await async_setup_entry(hass, config_entry)


async def test_on_data(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test on_data."""

    mock_client = MagicMock(spec=Client)
    connector = Connector(hass, config_entry, mock_client)

    # test CHARGE_POINTS
    data = {
        "object": "CHARGE_POINTS",
        "data": [{"evse_id": "101", "model_type": "hidden", "name": ""}],
    }
    await connector.on_data(data)
    assert connector.charge_points == {"101": {"model_type": "hidden", "name": ""}}

    # test CH_STATUS
    data2 = {
        "object": "CH_STATUS",
        "data": {
            "actual_v1": 12,
            "actual_v2": 14,
            "actual_v3": 15,
            "actual_p1": 12,
            "actual_p2": 14,
            "actual_p3": 15,
            "activity": "charging",
            "start_datetime": "2021-11-18T14:12:23",
            "stop_datetime": "2021-11-18T14:32:23",
            "offline_since": "2021-11-18T14:32:23",
            "total_cost": 10.52,
            "vehicle_status": "standby",
            "actual_kwh": 10,
            "evse_id": "101",
        },
    }
    await connector.on_data(data2)
    assert connector.charge_points == {
        "101": {
            "model_type": "hidden",
            "name": "",
            "actual_v1": 12,
            "actual_v2": 14,
            "actual_v3": 15,
            "actual_p1": 12,
            "actual_p2": 14,
            "actual_p3": 15,
            "activity": "charging",
            "start_datetime": "2021-11-18T14:12:23",
            "stop_datetime": "2021-11-18T14:32:23",
            "offline_since": "2021-11-18T14:32:23",
            "total_cost": 10.52,
            "vehicle_status": "standby",
            "actual_kwh": 10,
        }
    }

    # test GRID_STATUS
    data3 = {
        "object": "GRID_STATUS",
        "data": {
            "grid_actual_p1": 12,
            "grid_actual_p2": 14,
            "grid_actual_p3": 15,
        },
    }
    await connector.on_data(data3)
    assert connector.grid == {
        "grid_actual_p1": 12,
        "grid_actual_p2": 14,
        "grid_actual_p3": 15,
    }


async def test_start_loop(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test start_loop."""

    mock_client = MagicMock(spec=Client)
    mock_client.start_loop.side_effect = WebsocketError

    connector = Connector(hass, config_entry, mock_client)

    await connector.start_loop()
    future = utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert mock_client.connect.call_count == 1


async def test_reconnect(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Tests reconnect."""

    mock_client = MagicMock(spec=Client)
    connector = Connector(hass, config_entry, mock_client)

    await connector.reconnect()
    await hass.async_block_till_done()

    assert mock_client.start_loop.call_count == 1


async def test_reconnect_websocket_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconnect when connect throws a WebsocketError."""

    mock_client = MagicMock(spec=Client)
    connector = Connector(hass, config_entry, mock_client)

    mock_client.connect.side_effect = WebsocketError

    await connector.reconnect()

    future = utcnow() + timedelta(minutes=20)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert mock_client.connect.call_count == 2


async def test_reconnect_request_limit_reached_error(hass: HomeAssistant) -> None:
    """Test reconnect when connect throws a RequestLimitReached."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="uuid",
        unique_id="uuid",
        data={"api_token": "123", "card": {"123"}},
    )

    mock_client = MagicMock(spec=Client)
    connector = Connector(hass, config_entry, mock_client)

    # Request limit reached.
    mock_client.connect.side_effect = RequestLimitReached
    mock_client.get_next_reset_delta.return_value = timedelta(minutes=5)

    await connector.reconnect()
    await hass.async_block_till_done()

    mock_client.get_next_reset_delta.assert_called_once()

    future = utcnow() + timedelta(minutes=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert mock_client.connect.call_count == 2
