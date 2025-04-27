"""Tests for the STIEBEL ELTRON integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.stiebel_eltron.const import CONF_HUB, DEFAULT_HUB, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("mock_stiebel_eltron_client")
async def test_async_setup_success(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test successful async_setup."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: DEFAULT_HUB,
        },
        "modbus": [
            {
                CONF_NAME: DEFAULT_HUB,
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 502,
            }
        ],
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Verify the issue is created
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue
    assert issue.active is True
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_stiebel_eltron_client")
async def test_async_setup_already_configured(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry,
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: DEFAULT_HUB,
        },
        "modbus": [
            {
                CONF_NAME: DEFAULT_HUB,
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 502,
            }
        ],
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Verify the issue is created
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue
    assert issue.active is True
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_async_setup_with_non_existing_hub(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test async_setup with non-existing modbus hub."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: "non_existing_hub",
        },
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Verify the issue is created
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_missing_hub"
    )
    assert issue
    assert issue.active is True
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.translation_key == "deprecated_yaml_import_issue_missing_hub"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_async_setup_import_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_stiebel_eltron_client: AsyncMock,
) -> None:
    """Test async_setup with import failure."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: DEFAULT_HUB,
        },
        "modbus": [
            {
                CONF_NAME: DEFAULT_HUB,
                CONF_HOST: "invalid_host",
                CONF_PORT: 502,
            }
        ],
    }

    # Simulate an import failure
    mock_stiebel_eltron_client.update.side_effect = Exception("Import failure")

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Verify the issue is created
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_unknown"
    )
    assert issue
    assert issue.active is True
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.translation_key == "deprecated_yaml_import_issue_unknown"
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_modbus")
async def test_async_setup_cannot_connect(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_stiebel_eltron_client: AsyncMock,
) -> None:
    """Test async_setup with import failure."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: DEFAULT_HUB,
        },
        "modbus": [
            {
                CONF_NAME: DEFAULT_HUB,
                CONF_HOST: "invalid_host",
                CONF_PORT: 502,
            }
        ],
    }

    # Simulate a cannot connect error
    mock_stiebel_eltron_client.update.return_value = False

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Verify the issue is created
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue
    assert issue.active is True
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.translation_key == "deprecated_yaml_import_issue_cannot_connect"
    assert issue.severity == ir.IssueSeverity.WARNING
