"""Fixtures for UniFi Network methods."""
from __future__ import annotations

from unittest.mock import patch

from aiounifi.models.message import MessageKey
from aiounifi.websocket import WebsocketSignal, WebsocketState
import pytest

from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_unifi_websocket():
    """No real websocket allowed."""
    with patch("aiounifi.controller.WSClient") as mock:

        def make_websocket_call(
            *,
            message: MessageKey | None = None,
            data: list[dict] | dict | None = None,
            state: WebsocketState | None = None,
        ):
            """Generate a websocket call."""
            if data and not message:
                mock.return_value.data = data
                mock.call_args[1]["callback"](WebsocketSignal.DATA)
            elif data and message:
                if not isinstance(data, list):
                    data = [data]
                mock.return_value.data = {
                    "meta": {"message": message.value},
                    "data": data,
                }
                mock.call_args[1]["callback"](WebsocketSignal.DATA)
            elif state:
                mock.return_value.state = state
                mock.call_args[1]["callback"](WebsocketSignal.CONNECTION_STATE)
            else:
                raise NotImplementedError

        yield make_websocket_call


@pytest.fixture(autouse=True)
def mock_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow._async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock


@pytest.fixture
def mock_device_registry(hass):
    """Mock device registry."""
    dev_reg = dr.async_get(hass)
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate(
        (
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
            "00:00:00:00:00:03",
            "00:00:00:00:00:04",
            "00:00:00:00:00:05",
            "00:00:00:00:01:01",
            "00:00:00:00:02:02",
        )
    ):
        dev_reg.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )
