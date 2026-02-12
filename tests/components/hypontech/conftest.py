"""Common fixtures for the Hypontech Cloud tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hypontech.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hypontech.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
        unique_id="mock_account_id_123",
    )


@pytest.fixture
def create_entry(hass: HomeAssistant) -> Callable[..., MockConfigEntry]:
    """Return a factory for creating config entries."""

    def _create_entry(
        username: str = "test@example.com",
        password: str = "test-password",
        unique_id: str = "mock_account_id_123",
    ) -> MockConfigEntry:
        """Create a config entry with custom parameters."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
            unique_id=unique_id,
        )
        entry.add_to_hass(hass)
        return entry

    return _create_entry


@pytest.fixture
def mock_hyponcloud() -> Generator[AsyncMock]:
    """Mock HyponCloud."""
    with (
        patch(
            "homeassistant.components.hypontech.HyponCloud.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hypontech.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_overview",
        ) as mock_get_overview,
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_list",
        ) as mock_get_list,
    ):
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "mock_account_id_123"
        mock_get_admin_info.return_value = mock_admin_info
        mock_get_overview.return_value = AsyncMock()
        mock_get_list.return_value = []
        yield mock_get_overview
