"""Tests for the Quantum Gateway device tracker."""

from unittest.mock import MagicMock

import pytest
from requests import RequestException

from homeassistant import config_entries
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.quantum_gateway.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONFIG, MOCK_DEVICE_DATA

from tests.common import MockConfigEntry


async def test_device_tracker_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scanner: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == DOMAIN
    ]
    assert len(entries) == len(MOCK_DEVICE_DATA)

    entity_ids = {entry.entity_id for entry in entries}
    assert any(
        entity_id.startswith("device_tracker.desktop") for entity_id in entity_ids
    )
    assert any(
        entity_id.startswith("device_tracker.quantum_gateway_ff_ff_ff_ff_ff_ff")
        for entity_id in entity_ids
    )


async def test_setup_scanner_legacy_platform_imports_config_entry(
    hass: HomeAssistant,
    mock_scanner: MagicMock,
) -> None:
    """Test legacy device tracker setup triggers config flow import."""
    assert await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == MOCK_CONFIG
    assert entries[0].source == config_entries.SOURCE_IMPORT


@pytest.mark.parametrize(
    ("side_effect", "success_init", "issue_id"),
    [
        (
            RequestException("example error"),
            True,
            "yaml_import_cannot_connect",
        ),
        (
            None,
            False,
            "yaml_import_invalid_auth",
        ),
    ],
)
async def test_setup_scanner_legacy_platform_creates_issue(
    hass: HomeAssistant,
    issue_registry: IssueRegistry,
    mock_scanner: MagicMock,
    side_effect: RequestException | None,
    success_init: bool,
    issue_id: str,
) -> None:
    """Test issue is created when import cannot connect."""
    mock_scanner.side_effect = side_effect
    mock_scanner.return_value.success_init = success_init

    assert await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)

    assert issue is not None
    assert issue.translation_key == issue_id
    assert issue.translation_placeholders == {"host": MOCK_CONFIG[CONF_HOST]}
