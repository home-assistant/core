"""Fixtures and test data for VegeHub test methods."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import vegehub

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

IP_ADDR = "192.168.0.100"
TEST_API_KEY = "1234567890ABCD"
UNIQUE_ID = "aabbccddeeff"
TEST_SERVER = "http://example.com"


@pytest.fixture
def mock_aiohttp_session():
    """Set up mocked client session."""
    mocker = AiohttpClientMocker()

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        mocker.post(
            f"http://{IP_ADDR}/api/config/get",
            json={"hub": {}, "api_key": TEST_API_KEY},
        )

        mocker.post(f"http://{IP_ADDR}/api/config/set", status=200)

        # Mock _get_device_info
        mocker.post(
            f"http://{IP_ADDR}/api/info/get", text=load_fixture("vegehub/info_hub.json")
        )
        yield mocker


@pytest.fixture
def mock_aiohttp_bad_session():
    """Set up mocked client session that returns bad data."""
    mocker = AiohttpClientMocker()

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        mocker.post(f"http://{IP_ADDR}/api/config/get", json={})

        mocker.post(f"http://{IP_ADDR}/api/config/set", status=200)

        # Mock _get_device_info
        mocker.post(
            f"http://{IP_ADDR}/api/info/get",
            json={},
        )
        yield mocker


@pytest.fixture
def mock_aiohttp_bad_session_404():
    """Set up mocked client session where responses are errors."""
    mocker = AiohttpClientMocker()

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        mocker.post(f"http://{IP_ADDR}/api/config/get", json={}, status=404)

        mocker.post(f"http://{IP_ADDR}/api/config/set", status=404)

        # Mock _get_device_info
        mocker.post(f"http://{IP_ADDR}/api/info/get", json={}, status=404)
        yield mocker


@pytest.fixture(name="basic_hub")
def fixture_basic_hub(mock_aiohttp_session):
    """Fixture for creating a VegeHub instance."""
    return vegehub.VegeHub(ip_address=IP_ADDR, unique_id=UNIQUE_ID)


@pytest.fixture
def config_entry(basic_hub):
    """Mock a config entry."""
    return MagicMock(
        data={"mac": "1234567890AB", "host": "VegeHub1"},
        runtime_data=basic_hub,
    )
