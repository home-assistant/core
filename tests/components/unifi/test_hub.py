"""Test UniFi Network."""

from http import HTTPStatus
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

import aiounifi
import pytest

from homeassistant.components.unifi.const import DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.unifi.hub import get_unifi_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import ConfigEntryFactoryType, WebsocketStateManager

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_hub_setup(
    device_registry: dr.DeviceRegistry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await config_entry_factory()

    assert len(forward_entry_setup.mock_calls) == 1
    assert forward_entry_setup.mock_calls[0][1] == (
        config_entry,
        [
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.IMAGE,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.UPDATE,
        ],
    )

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(UNIFI_DOMAIN, config_entry.unique_id)},
    )

    assert device_entry.sw_version == "7.4.162"


async def test_reset_after_successful_setup(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Calling reset when the entry has been setup."""
    assert config_entry_setup.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert config_entry_setup.state is ConfigEntryState.NOT_LOADED


async def test_reset_fails(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Calling reset when the entry has been setup can return false."""
    assert config_entry_setup.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(config_entry_setup.entry_id)
        assert config_entry_setup.state is ConfigEntryState.FAILED_UNLOAD


@pytest.mark.usefixtures("mock_device_registry")
async def test_connection_state_signalling(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_state: WebsocketStateManager,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify connection statesignalling and connection state are working."""
    client_payload.append(
        {
            "hostname": "client",
            "ip": "10.0.0.1",
            "is_wired": True,
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
            "mac": "00:00:00:00:00:01",
        }
    )
    await config_entry_factory()

    # Controller is connected
    assert hass.states.get("device_tracker.client").state == "home"

    await mock_websocket_state.disconnect()
    # Controller is disconnected
    assert hass.states.get("device_tracker.client").state == "unavailable"

    await mock_websocket_state.reconnect()
    # Controller is once again connected
    assert hass.states.get("device_tracker.client").state == "home"


async def test_reconnect_mechanism(
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Verify reconnect prints only on first reconnection try."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234/",
        status=HTTPStatus.BAD_GATEWAY,
    )

    await mock_websocket_state.disconnect()
    assert aioclient_mock.call_count == 0

    await mock_websocket_state.reconnect(fail=True)
    assert aioclient_mock.call_count == 1

    await mock_websocket_state.reconnect(fail=True)
    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        aiounifi.AiounifiException,
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_reconnect_mechanism_exceptions(
    mock_websocket_state: WebsocketStateManager,
    exception: Exception,
) -> None:
    """Verify async_reconnect calls expected methods."""
    with (
        patch("aiounifi.Controller.login", side_effect=exception),
        patch(
            "homeassistant.components.unifi.hub.hub.UnifiWebsocket.reconnect"
        ) as mock_reconnect,
    ):
        await mock_websocket_state.disconnect()

        await mock_websocket_state.reconnect()
        mock_reconnect.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "raised_exception"),
    [
        (TimeoutError, CannotConnect),
        (aiounifi.BadGateway, CannotConnect),
        (aiounifi.Forbidden, CannotConnect),
        (aiounifi.ServiceUnavailable, CannotConnect),
        (aiounifi.RequestError, CannotConnect),
        (aiounifi.ResponseError, CannotConnect),
        (aiounifi.Unauthorized, AuthenticationRequired),
        (aiounifi.LoginRequired, AuthenticationRequired),
        (aiounifi.AiounifiException, AuthenticationRequired),
    ],
)
async def test_get_unifi_api_fails_to_connect(
    hass: HomeAssistant,
    side_effect: Exception,
    raised_exception: Exception,
    config_entry_data: MappingProxyType[str, Any],
) -> None:
    """Check that get_unifi_api can handle UniFi Network being unavailable."""
    with (
        patch("aiounifi.Controller.login", side_effect=side_effect),
        pytest.raises(raised_exception),
    ):
        await get_unifi_api(hass, config_entry_data)
