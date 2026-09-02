"""Tests for the Sky Hub device tracker."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant.components.sky_hub.const import DOMAIN
from homeassistant.components.sky_hub.device_tracker import async_setup_scanner
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_DEVICES, MOCK_HOST

from tests.common import MockConfigEntry


async def test_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skyqhub: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test device tracker entities are created from the coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == DOMAIN
    ]
    assert len(entries) == 2

    entity_ids = {entry.entity_id for entry in entries}
    assert any(eid.startswith("device_tracker.my_phone") for eid in entity_ids)
    assert any(eid.startswith("device_tracker.my_laptop") for eid in entity_ids)


async def test_legacy_platform_imports_config_entry(
    hass: HomeAssistant, mock_skyqhub: MagicMock
) -> None:
    """Test the legacy device_tracker platform imports a config entry."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, CONF_HOST: MOCK_HOST}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_HOST: MOCK_HOST}
    assert entries[0].source == SOURCE_IMPORT


async def test_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant, mock_skyqhub: MagicMock, issue_registry: IssueRegistry
) -> None:
    """Test an issue is raised when the legacy YAML import cannot connect."""
    mock_skyqhub.return_value.async_get_skyhub_data.return_value = None

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, CONF_HOST: MOCK_HOST}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": MOCK_HOST}


@pytest.mark.parametrize(
    "side_effect",
    [None, aiohttp.ClientError],
    ids=["returns_none", "raises_client_error"],
)
async def test_setup_entry_retries_when_hub_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skyqhub: MagicMock,
    side_effect: type[Exception] | None,
) -> None:
    """Test the config entry retries when the hub returns no data or errors."""
    mock_skyqhub.return_value.async_get_skyhub_data.return_value = None
    mock_skyqhub.return_value.async_get_skyhub_data.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_legacy_import_clears_stale_cannot_connect_issue(
    hass: HomeAssistant, mock_skyqhub: MagicMock, issue_registry: IssueRegistry
) -> None:
    """Test a successful YAML import removes a stale cannot_connect repair issue."""
    config = {CONF_HOST: MOCK_HOST}

    # A first import that cannot connect raises the repair issue.
    mock_skyqhub.return_value.async_get_skyhub_data.return_value = None
    assert not await async_setup_scanner(hass, config, AsyncMock())
    assert (
        issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect") is not None
    )

    # A later successful import clears it.
    mock_skyqhub.return_value.async_get_skyhub_data.return_value = MOCK_DEVICES
    assert await async_setup_scanner(hass, config, AsyncMock())
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect") is None
