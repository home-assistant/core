"""Tests for PoolsideClient's optimistic desired-state tracking."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant.components.poolside.client import (
    PoolsideClient,
    PoolsideCommandError,
    PoolsideConnectionError,
)


@pytest.fixture
def send_request() -> AsyncMock:
    """A stub for PoolsideClient.async_send_request (no real connection)."""
    return AsyncMock(return_value=True)


@pytest.fixture
def client(send_request: AsyncMock) -> PoolsideClient:
    """A PoolsideClient with async_send_request stubbed out (no real connection)."""
    instance = PoolsideClient(
        session=MagicMock(spec=aiohttp.ClientSession),
        host="192.168.1.50",
        port=8126,
        client_private_key=b"\x01" * 32,
        controller_public_key=b"\x02" * 32,
        controller_uuid="controller-1",
    )
    instance.async_send_request = send_request  # type: ignore[method-assign]
    return instance


async def test_set_desired_state_records_optimistic_status(
    client: PoolsideClient,
) -> None:
    """A successful write is recorded under the control's own UUID."""
    await client.async_set_desired_state("control-1", Status="ON", PowerLevel="75")

    assert client.get_status("control-1", "Status") == "ON"
    assert client.get_status("control-1", "PowerLevel") == "75"


async def test_set_desired_state_notifies_subscribers(client: PoolsideClient) -> None:
    """Subscribers for the control's UUID are notified after a successful write."""
    calls = []
    client.subscribe_status("control-1", lambda: calls.append(True))

    await client.async_set_desired_state("control-1", Status="ON")

    assert calls == [True]


async def test_set_desired_state_sends_batch_and_control_uuid(
    client: PoolsideClient, send_request: AsyncMock
) -> None:
    """The JSON-RPC call carries a fresh BatchUUID and the target ControlUUID."""
    await client.async_set_desired_state("control-1", Status="ON")

    method, params = send_request.call_args.args
    assert method == "Device.setDesiredState2"
    assert params["DesiredStates"] == [{"ControlUUID": "control-1", "Status": "ON"}]
    assert "BatchUUID" in params


async def test_refresh_status_calls_get_status(
    client: PoolsideClient, send_request: AsyncMock
) -> None:
    """async_refresh_status calls the bare Device.getStatus (no Items filter)."""
    send_request.return_value = []

    await client.async_refresh_status()

    send_request.assert_awaited_with("Device.getStatus", {})


async def test_refresh_status_applies_every_returned_item(
    client: PoolsideClient, send_request: AsyncMock
) -> None:
    """Every item in the getStatus response is applied, as if it were a push."""
    send_request.return_value = [
        {"UUID": "control-1", "name": "ActualPowerState", "value": "ON"},
        {"UUID": "control-2", "name": "Temperature", "value": 79},
    ]

    await client.async_refresh_status()

    assert client.get_status("control-1", "ActualPowerState") == "ON"
    assert client.get_status("control-2", "Temperature") == 79


@pytest.mark.parametrize(
    "error", [PoolsideConnectionError("offline"), PoolsideCommandError("rejected")]
)
async def test_refresh_status_swallows_errors(
    client: PoolsideClient, send_request: AsyncMock, error: Exception
) -> None:
    """A failed getStatus call is logged, not raised - it shouldn't break connect()."""
    send_request.side_effect = error

    await client.async_refresh_status()
