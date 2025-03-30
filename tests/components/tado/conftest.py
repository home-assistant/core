"""Fixtures for Tado tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from PyTado.http import DeviceActivationStatus
import pytest

from homeassistant.components.tado import CONF_REFRESH_TOKEN, DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_tado_api() -> Generator[MagicMock]:
    """Mock the Tado API."""
    with (
        patch("homeassistant.components.tado.Tado") as mock_tado,
        patch("homeassistant.components.tado.config_flow.Tado", new=mock_tado),
    ):
        client = mock_tado.return_value
        client.device_verification_url.return_value = (
            "https://login.tado.com/oauth2/device?user_code=TEST"
        )
        client.device_activation_status.return_value = DeviceActivationStatus.COMPLETED
        client.get_me.return_value = load_json_object_fixture("me.json", DOMAIN)
        client.get_refresh_token.return_value = "refresh"
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.tado.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_REFRESH_TOKEN: "refresh",
        },
        unique_id="1",
        version=2,
    )
