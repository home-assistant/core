"""Common fixtures for the energenie_mi_home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.energenie_mi_home.api import MiHomeDevice
from homeassistant.components.energenie_mi_home.const import (
    DEVICE_TYPE_LIGHT_SWITCH,
    DEVICE_TYPE_POWER_SOCKET,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.energenie_mi_home.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mihome_api() -> MagicMock:
    """Mock MiHome API client."""
    api = MagicMock()
    api.async_authenticate = AsyncMock(return_value="test-api-key")
    api.async_get_devices = AsyncMock(
        return_value=[
            MiHomeDevice(
                device_id="1",
                name="Light Switch 1",
                device_type=DEVICE_TYPE_LIGHT_SWITCH,
                is_on=True,
                available=True,
                product_type="elight",
            ),
            MiHomeDevice(
                device_id="2",
                name="Power Socket 1",
                device_type=DEVICE_TYPE_POWER_SOCKET,
                is_on=False,
                available=True,
                product_type="ecalm",
            ),
        ]
    )
    api.async_set_device_state = AsyncMock()
    return api


def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="test@example.com",
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_API_KEY: "test-api-key",
        },
        unique_id="test@example.com",
    )
