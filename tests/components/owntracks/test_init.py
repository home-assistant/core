"""Test the owntracks_http platform."""

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components import owntracks
from homeassistant.components.device_tracker.legacy import Device
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_component
from tests.typing import ClientSessionGenerator

MINIMAL_LOCATION_MESSAGE = {
    "_type": "location",
    "lon": 45,
    "lat": 90,
    "p": 101.3977584838867,
    "tid": "test",
    "tst": 1,
}

LOCATION_MESSAGE = {
    "_type": "location",
    "acc": 60,
    "alt": 27,
    "batt": 92,
    "cog": 248,
    "lon": 45,
    "lat": 90,
    "p": 101.3977584838867,
    "tid": "test",
    "t": "u",
    "tst": 1,
    "vac": 4,
    "vel": 0,
}


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf: list[Device]) -> None:
    """Mock device tracker config loading."""


@pytest.fixture
def mock_client(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    mock_component(hass, "group")
    mock_component(hass, "zone")
    mock_component(hass, "device_tracker")

    MockConfigEntry(
        domain="owntracks", data={"webhook_id": "owntracks_test", "secret": "abcd"}
    ).add_to_hass(hass)
    hass.loop.run_until_complete(async_setup_component(hass, "owntracks", {}))

    return hass.loop.run_until_complete(hass_client_no_auth())


async def test_handle_valid_message(mock_client) -> None:
    """Test that we forward messages correctly to OwnTracks."""
    resp = await mock_client.post(
        "/api/webhook/owntracks_test",
        json=LOCATION_MESSAGE,
        headers={"X-Limit-u": "Paulus", "X-Limit-d": "Pixel"},
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == []


async def test_handle_valid_minimal_message(mock_client) -> None:
    """Test that we forward messages correctly to OwnTracks."""
    resp = await mock_client.post(
        "/api/webhook/owntracks_test",
        json=MINIMAL_LOCATION_MESSAGE,
        headers={"X-Limit-u": "Paulus", "X-Limit-d": "Pixel"},
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == []


async def test_handle_value_error(mock_client) -> None:
    """Test we don't disclose that this is a valid webhook."""
    resp = await mock_client.post(
        "/api/webhook/owntracks_test",
        json="",
        headers={"X-Limit-u": "Paulus", "X-Limit-d": "Pixel"},
    )

    assert resp.status == 200

    json = await resp.text()
    assert json == ""


async def test_returns_error_missing_username(
    mock_client, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an error is returned when username is missing."""
    resp = await mock_client.post(
        "/api/webhook/owntracks_test",
        json=LOCATION_MESSAGE,
        headers={"X-Limit-d": "Pixel"},
    )

    # Needs to be 200 or OwnTracks keeps retrying bad packet.
    assert resp.status == 200
    json = await resp.json()
    assert json == []
    assert "No topic or user found" in caplog.text


async def test_returns_error_incorrect_json(
    mock_client, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an error is returned when username is missing."""
    resp = await mock_client.post(
        "/api/webhook/owntracks_test", data="not json", headers={"X-Limit-d": "Pixel"}
    )

    # Needs to be 200 or OwnTracks keeps retrying bad packet.
    assert resp.status == 200
    json = await resp.json()
    assert json == []
    assert "invalid JSON" in caplog.text


async def test_returns_error_missing_device(mock_client) -> None:
    """Test that an error is returned when device name is missing."""
    resp = await mock_client.post(
        "/api/webhook/owntracks_test",
        json=LOCATION_MESSAGE,
        headers={"X-Limit-u": "Paulus"},
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == []


def test_context_delivers_pending_msg() -> None:
    """Test that context is able to hold pending messages while being init."""
    context = owntracks.OwnTracksContext(None, None, None, None, None, None, None, None)
    context.async_see(hello="world")
    context.async_see(world="hello")
    received = []

    context.set_async_see(lambda **data: received.append(data))

    assert len(received) == 2
    assert received[0] == {"hello": "world"}
    assert received[1] == {"world": "hello"}

    received.clear()

    context.set_async_see(lambda **data: received.append(data))
    assert len(received) == 0
