"""Tests for the Atomberg API client."""

from http import HTTPStatus

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.atomberg.api import (
    API_URL,
    AtombergAuthError,
    AtombergClient,
    AtombergConnectionError,
    AtombergError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

TOKEN_URL = f"{API_URL}/v1/get_access_token"
DEVICES_URL = f"{API_URL}/v1/get_list_of_devices"
COMMAND_URL = f"{API_URL}/v1/send_command"
TOKEN_RESPONSE = {"status": "Success", "message": {"access_token": "access-1"}}


def _client(hass: HomeAssistant) -> AtombergClient:
    return AtombergClient(async_get_clientsession(hass), "key", "refresh")


async def test_token_is_reused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test one token request serves several calls and headers are set."""
    aioclient_mock.get(TOKEN_URL, json=TOKEN_RESPONSE)
    aioclient_mock.get(
        DEVICES_URL, json={"status": "Success", "message": {"devices_list": []}}
    )
    client = _client(hass)

    await client.async_get_devices()
    await client.async_get_devices()

    assert len([c for c in aioclient_mock.mock_calls if str(c[1]) == TOKEN_URL]) == 1
    token_headers = aioclient_mock.mock_calls[0][3]
    assert token_headers["Authorization"] == "Bearer refresh"
    assert token_headers["x-api-key"] == "key"
    assert aioclient_mock.mock_calls[1][3]["Authorization"] == "Bearer access-1"


async def test_rejected_access_token_refreshes_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a 401 triggers exactly one token refresh and retry before failing."""
    aioclient_mock.get(TOKEN_URL, json=TOKEN_RESPONSE)
    aioclient_mock.get(DEVICES_URL, status=HTTPStatus.UNAUTHORIZED)

    with pytest.raises(AtombergAuthError):
        await _client(hass).async_get_devices()

    assert len([c for c in aioclient_mock.mock_calls if str(c[1]) == TOKEN_URL]) == 2
    assert len([c for c in aioclient_mock.mock_calls if str(c[1]) == DEVICES_URL]) == 2


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (HTTPStatus.UNAUTHORIZED, AtombergAuthError),
        (HTTPStatus.FORBIDDEN, AtombergAuthError),
        (HTTPStatus.INTERNAL_SERVER_ERROR, AtombergConnectionError),
    ],
)
async def test_token_request_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    exception: type[AtombergError],
) -> None:
    """Test token endpoint errors map to the right exception."""
    aioclient_mock.get(TOKEN_URL, status=status)

    with pytest.raises(exception):
        await _client(hass).async_get_devices()


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a network failure maps to a connection error."""
    aioclient_mock.get(TOKEN_URL, exc=TimeoutError)

    with pytest.raises(AtombergConnectionError):
        await _client(hass).async_get_devices()


@pytest.mark.parametrize(
    "body",
    [
        {"status": "Failure", "message": "nope"},
        {"status": "Success", "message": {"unexpected": []}},
    ],
)
async def test_bad_device_list(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, body: dict
) -> None:
    """Test unexpected device list responses raise."""
    aioclient_mock.get(TOKEN_URL, json=TOKEN_RESPONSE)
    aioclient_mock.get(DEVICES_URL, json=body)

    with pytest.raises(AtombergError):
        await _client(hass).async_get_devices()


async def test_send_command_payload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the command request body."""
    aioclient_mock.get(TOKEN_URL, json=TOKEN_RESPONSE)
    aioclient_mock.post(COMMAND_URL, json={"status": "Success", "message": {}})

    await _client(hass).async_send_command("abc", {"speed": 4})

    assert aioclient_mock.mock_calls[-1][2] == {
        "device_id": "abc",
        "command": {"speed": 4},
    }


@pytest.mark.parametrize(
    ("window", "expected_body"),
    [
        ((None, None), {"device_id": "abc"}),
        ((10, 20), {"device_id": "abc", "start_time": 10, "end_time": 20}),
    ],
)
async def test_guest_pin_request(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    window: tuple[int | None, int | None],
    expected_body: dict,
) -> None:
    """Test the guest PIN request body and response parsing."""
    aioclient_mock.get(TOKEN_URL, json=TOKEN_RESPONSE)
    aioclient_mock.post(
        f"{API_URL}/v1/get_lock_dynamic_pin",
        json={"status": "Success", "message": {"data": {"otp": "123456"}}},
    )

    pin = await _client(hass).async_get_guest_pin("abc", *window)

    assert pin == {"otp": "123456"}
    assert aioclient_mock.mock_calls[-1][2] == expected_body


async def test_guest_pin_bad_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a response without PIN data raises."""
    aioclient_mock.get(TOKEN_URL, json=TOKEN_RESPONSE)
    aioclient_mock.post(
        f"{API_URL}/v1/get_lock_dynamic_pin",
        json={"status": "Success", "message": {}},
    )

    with pytest.raises(AtombergError):
        await _client(hass).async_get_guest_pin("abc")
