"""Tests for the GPM init."""

import logging
import re

import pytest

from homeassistant.components.gpm import RepositoryType
from homeassistant.components.gpm._manager import IntegrationRepositoryManager
from homeassistant.components.gpm.const import CONF_UPDATE_STRATEGY, DOMAIN
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_remove_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test async_remove_entry."""
    assert DOMAIN in hass.config.components
    assert integration_manager.remove.await_count == 0
    await hass.config_entries.async_remove(config_entry.entry_id)
    assert integration_manager.remove.await_count == 1


async def test_async_setup_entry_not_installed(
    hass: HomeAssistant,
    integration_manager: IntegrationRepositoryManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_setup_entry raises an error when repository is not installed."""
    assert await integration_manager.is_installed() is False
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: RepositoryType.INTEGRATION,
            CONF_URL: integration_manager.repo_url,
            CONF_UPDATE_STRATEGY: integration_manager.update_strategy,
        },
    )
    entry.add_to_hass(hass)
    with caplog.at_level(logging.ERROR):
        await hass.config_entries.async_setup(entry.entry_id)
        assert re.search(
            r"Repository .* not installed despite existing config entry", caplog.text
        )
