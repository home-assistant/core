"""Shared Karaca Connect tests fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.karaca_connect.const import CONF_DEVICE_ID, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A Karaca device using placeholder credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Karaca tea maker",
        unique_id="karaca_device-123",
        data={
            CONF_EMAIL: "example@example.invalid",
            CONF_PASSWORD: "placeholder",
            CONF_DEVICE_ID: "device-123",
        },
    )


@pytest.fixture
def mock_karaca_client() -> Generator[AsyncMock]:
    """Avoid making network requests to Karaca."""
    with (
        patch(
            "homeassistant.components.karaca_connect.KaracaClient",
            autospec=True,
        ) as client_class,
        patch(
            "homeassistant.components.karaca_connect.config_flow.KaracaClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.login = AsyncMock()
        client.get_devices = AsyncMock(
            return_value=[{"id": "device-123", "label": "Karaca tea maker"}]
        )
        client.get_detail = AsyncMock(
            return_value={
                "detail": {"mode": 1, "modeName": "standby"},
                "meta": {"connected": True},
            }
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent automatic setup during configuration flow tests."""
    with patch(
        "homeassistant.components.karaca_connect.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup
