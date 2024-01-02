"""Test Blue Current Init Component."""

from datetime import timedelta
from unittest.mock import patch

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

from . import init_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test load and unload entry."""
    config_entry = await init_integration(hass, "sensor", {})
    assert config_entry.state == ConfigEntryState.LOADED
    assert isinstance(hass.data[DOMAIN][config_entry.entry_id], Connector)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert hass.data[DOMAIN] == {}


@pytest.mark.parametrize(
    ("api_error", "config_error"),
    [
        (InvalidApiToken, ConfigEntryAuthFailed),
        (BlueCurrentException, ConfigEntryNotReady),
    ],
)
async def test_config_exceptions(
    hass: HomeAssistant, api_error: BlueCurrentException, config_error: IntegrationError
) -> None:
    """Tests if the correct config error is raised when connecting to the api fails."""
    with patch(
        "homeassistant.components.blue_current.Client.connect",
        side_effect=api_error,
    ), pytest.raises(config_error):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={"api_token": "123", "card": {"123"}},
        )
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)


async def test_on_data(hass: HomeAssistant) -> None:
    """Test on_data."""

    await init_integration(hass, "sensor", {})

    with patch(
        "homeassistant.components.blue_current.async_dispatcher_send"
    ) as test_async_dispatcher_send:
        connector: Connector = hass.data[DOMAIN]["uuid"]

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

        test_async_dispatcher_send.assert_called_with(
            hass, "blue_current_value_update_101"
        )

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
        test_async_dispatcher_send.assert_called_with(hass, "blue_current_grid_update")


async def test_start_loop(hass: HomeAssistant) -> None:
    """Tests start_loop."""

    with patch(
        "homeassistant.components.blue_current.async_call_later"
    ) as test_async_call_later:
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={"api_token": "123", "card": {"123"}},
        )

        connector = Connector(hass, config_entry, Client)

        with patch(
            "homeassistant.components.blue_current.Client.start_loop",
            side_effect=WebsocketError("unknown command"),
        ):
            await connector.start_loop()
            test_async_call_later.assert_called_with(hass, 1, connector.reconnect)

        with patch(
            "homeassistant.components.blue_current.Client.start_loop",
            side_effect=RequestLimitReached,
        ):
            await connector.start_loop()
            test_async_call_later.assert_called_with(hass, 1, connector.reconnect)


async def test_reconnect(hass: HomeAssistant) -> None:
    """Tests reconnect."""

    with patch(
        "homeassistant.components.blue_current.async_call_later"
    ) as test_async_call_later:
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={"api_token": "123", "card": {"123"}},
        )

        connector = Connector(hass, config_entry, Client)

        with patch(
            "homeassistant.components.blue_current.Client.connect",
            side_effect=WebsocketError,
        ):
            await connector.reconnect()

        test_async_call_later.assert_called_with(hass, 20, connector.reconnect)

        with patch(
            "homeassistant.components.blue_current.Client.connect",
            side_effect=RequestLimitReached,
        ), patch(
            "homeassistant.components.blue_current.Client.get_next_reset_delta",
            return_value=timedelta(hours=1),
        ):
            await connector.reconnect()

        test_async_call_later.assert_called_with(
            hass, timedelta(hours=1), connector.reconnect
        )

        with patch("homeassistant.components.blue_current.Client.connect"), patch(
            "homeassistant.components.blue_current.Connector.start_loop"
        ) as test_start_loop, patch(
            "homeassistant.components.blue_current.Client.get_charge_points"
        ) as test_get_charge_points:
            await connector.reconnect()
            test_start_loop.assert_called_once()
            test_get_charge_points.assert_called_once()
