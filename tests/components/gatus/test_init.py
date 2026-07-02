"""Tests for the Gatus integration setup and unload lifecycle."""

import json
from unittest.mock import AsyncMock

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_fixture


async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test standard successful setup and unload cycle of the integration."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_success.json"
    )
    mock_data = json.loads(fixture_data)

    mock_gatus_client.get_endpoints_statuses.return_value = mock_data

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: "http://gatus.local:8080"}
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert isinstance(config_entry.runtime_data, GatusDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_failing_first_refresh(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
) -> None:
    """Test setup failure when the initial coordinator data fetch fails."""
    mock_gatus_client.get_endpoints_statuses.side_effect = Exception(
        "Connection timed out"
    )

    config_entry = await setup_integration(hass, mock_gatus_client, [])

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
