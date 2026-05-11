"""Test configuration and fixtures for Imou integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.imou.const import DOMAIN
from homeassistant.core import HomeAssistant

from .util import CONFIG_ENTRY_DATA, async_init_integration

from tests.common import MockConfigEntry

_BUTTON_PRESS_SERVICE_IGNORE = "component.button.services.press."


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Ignore button.press translations only when that service is registered.

    Config flow tests do not load the button platform; failed setup skips it too.
    """
    if request.node.name in ("test_setup_entry_success", "test_unload_entry"):
        return [_BUTTON_PRESS_SERVICE_IGNORE]
    return []


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Imou",
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA,
        unique_id=CONFIG_ENTRY_DATA["app_id"],
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_api_client() -> Generator[MagicMock]:
    """Create a mock API client."""
    with patch(
        "homeassistant.components.imou.config_flow.ImouOpenApiClient"
    ) as mock_client:
        mock_instance = AsyncMock()
        mock_instance.async_get_token = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.imou.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    return await async_init_integration(hass, mock_config_entry)
