"""MadVR conftest for shared testing setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.madvr.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import MOCK_CONFIG, MOCK_MAC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.madvr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_madvr_client() -> Generator[AsyncMock, None, None]:
    """Mock a MadVR client."""
    with (
        patch(
            "homeassistant.components.madvr.config_flow.Madvr", autospec=True
        ) as mock_client,
        patch("homeassistant.components.madvr.Madvr", new=mock_client),
    ):
        client = mock_client.return_value
        client.host = MOCK_CONFIG[CONF_HOST]
        client.port = MOCK_CONFIG[CONF_PORT]
        client.mac_address = MOCK_MAC
        client.connected.return_value = True
        client.is_device_connectable.return_value = True
        client.loop = AsyncMock()
        client.tasks = AsyncMock()
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_MAC,
        title=DEFAULT_NAME,
    )
