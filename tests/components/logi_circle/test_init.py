"""Tests for the Logi Circle integration."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.logi_circle import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.fixture(name="disable_platforms")
async def disable_platforms_fixture(hass):
    """Disable logi_circle platforms."""
    with patch("homeassistant.components.logi_circle.PLATFORMS", []):
        yield


@pytest.fixture
def mock_logi_circle():
    """Mock logi_circle."""

    auth_provider_mock = Mock()
    auth_provider_mock.close = AsyncMock()
    auth_provider_mock.clear_authorization = AsyncMock()

    with patch("homeassistant.components.logi_circle.LogiCircle") as logi_circle:
        future = asyncio.Future()
        future.set_result({"accountId": "testId"})
        LogiCircle = logi_circle()
        LogiCircle.auth_provider = auth_provider_mock
        LogiCircle.synchronize_cameras = AsyncMock()
        yield LogiCircle


async def test_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    disable_platforms,
    mock_logi_circle,
) -> None:
    """Test the LogiCircle configuration entry loading/unloading handles the repair."""
    config_entry = MockConfigEntry(
        title="Example 1",
        domain=DOMAIN,
        data={
            "api_key": "blah",
            "client_id": "blah",
            "client_secret": "blah",
            "redirect_uri": "blah",
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)

    # Remove the entry
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN) is None
