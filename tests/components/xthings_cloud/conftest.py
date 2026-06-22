"""Fixtures for Xthings Cloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.xthings_cloud.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_TOKEN

from .const import MOCK_EMAIL, MOCK_REFRESH_TOKEN, MOCK_TOKEN, MOCK_USER_ID

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_EMAIL,
        data={
            CONF_EMAIL: MOCK_EMAIL,
            CONF_TOKEN: MOCK_TOKEN,
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
        },
        unique_id=MOCK_USER_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.xthings_cloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def device_fixtures() -> list[str]:
    """Fixtures for Xthings Cloud devices."""
    return [
        "XT-LT050",
        "XT-LT100",
        "XT-LT200",
        "XT-PL50",
        "XT-PL100",
        "XT-LK50",
    ]


@pytest.fixture
def mock_api_client(
    device_fixtures: list[str], mock_websocket: AsyncMock
) -> Generator[AsyncMock]:
    """Mock the XthingsCloudApiClient."""
    with (
        patch(
            "homeassistant.components.xthings_cloud.config_flow.XthingsCloudApiClient",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.xthings_cloud.XthingsCloudApiClient",
            new=mock_cls,
        ),
    ):
        client = mock_cls.return_value
        client.async_login.return_value = {
            "token": MOCK_TOKEN,
            "refresh_token": MOCK_REFRESH_TOKEN,
            "user_id": MOCK_USER_ID,
            "client_id": "mock_client_id",
        }
        client.async_get_devices.return_value = [
            load_json_object_fixture(f"{device_fixture}.json", DOMAIN)
            for device_fixture in device_fixtures
        ]
        client.is_token_expired.return_value = False
        yield client


@pytest.fixture
def mock_websocket() -> Generator[AsyncMock]:
    """Mock the XthingsCloudWebSocket."""
    with patch(
        "homeassistant.components.xthings_cloud.coordinator.XthingsCloudWebSocket",
        autospec=True,
    ) as mock_ws_cls:
        yield mock_ws_cls


@pytest.fixture(autouse=True)
def mock_instance_id() -> Generator[None]:
    """Mock the instance ID."""
    with patch(
        "homeassistant.components.xthings_cloud.config_flow.async_get_instance_id",
        return_value="mock_instance_id",
    ):
        yield
