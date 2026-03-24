"""Common fixtures for html5 integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponse
import pytest

from homeassistant.components.html5.const import (
    ATTR_VAPID_EMAIL,
    ATTR_VAPID_PRV_KEY,
    ATTR_VAPID_PUB_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry, patch

MOCK_CONF = {
    ATTR_VAPID_EMAIL: "test@example.com",
    ATTR_VAPID_PRV_KEY: "h6acSRds8_KR8hT9djD8WucTL06Gfe29XXyZ1KcUjN8",
}
MOCK_CONF_PUB_KEY = "BIUtPN7Rq_8U7RBEqClZrfZ5dR9zPCfvxYPtLpWtRVZTJEc7lzv2dhzDU6Aw1m29Ao0-UA1Uq6XO9Df8KALBKqA"


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock ntfy configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HTML5",
        data={
            ATTR_VAPID_PRV_KEY: MOCK_CONF[ATTR_VAPID_PRV_KEY],
            ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
            ATTR_VAPID_EMAIL: MOCK_CONF[ATTR_VAPID_EMAIL],
            CONF_NAME: DOMAIN,
        },
        entry_id="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )


@pytest.fixture(name="load_config")
def mock_load_config() -> Generator[MagicMock]:
    """Mock load config."""

    with patch(
        "homeassistant.components.html5.notify._load_config", return_value={}
    ) as mock_load_config:
        yield mock_load_config


@pytest.fixture
def mock_wp() -> Generator[AsyncMock]:
    """Mock WebPusher."""

    with patch(
        "homeassistant.components.html5.notify.WebPusher", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.cls = mock_client
        client.send_async.return_value = AsyncMock(spec=ClientResponse, status=201)
        yield client


@pytest.fixture(name="webpush_async")
def mock_webpush_async() -> Generator[AsyncMock]:
    """Mock webpush_async."""

    with patch(
        "homeassistant.components.html5.notify.webpush_async", autospec=True
    ) as mock_client:
        mock_client.return_value = AsyncMock(spec=ClientResponse, status=201)
        yield mock_client


@pytest.fixture
def mock_jwt() -> Generator[MagicMock]:
    """Mock JWT."""

    with (
        patch("homeassistant.components.html5.notify.jwt") as mock_client,
    ):
        mock_client.encode.return_value = "JWT"
        mock_client.decode.return_value = {"target": "device"}
        yield mock_client


@pytest.fixture
def mock_uuid() -> Generator[MagicMock]:
    """Mock UUID."""

    with (
        patch("homeassistant.components.html5.notify.uuid") as mock_client,
    ):
        mock_client.uuid4.return_value = "12345678-1234-5678-1234-567812345678"
        yield mock_client


@pytest.fixture
def mock_vapid() -> Generator[MagicMock]:
    """Mock VAPID headers."""

    with (
        patch(
            "homeassistant.components.html5.notify.Vapid", autospec=True
        ) as mock_client,
    ):
        mock_client.from_string.return_value.sign.return_value = {
            "Authorization": "vapid t=signed!!!",
            "urgency": "normal",
            "priority": "normal",
        }
        yield mock_client
