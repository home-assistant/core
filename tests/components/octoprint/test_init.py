"""Tests for the OctoPrint integration setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyoctoprintapi import ApiError, DiscoverySettings
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.octoprint.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir, translation
from homeassistant.setup import async_setup_component

YAML_CONFIG = {
    DOMAIN: {
        "host": "1.1.1.1",
        "api_key": "test-key",
        "port": 81,
        "ssl": True,
        "path": "/",
    }
}


@pytest.fixture
def mock_discovery_info() -> Generator[AsyncMock]:
    """Mock the discovery info of the printer."""
    with patch(
        "pyoctoprintapi.OctoprintClient.get_discovery_info",
        return_value=DiscoverySettings({"upnpUuid": "uuid"}),
    ) as mock:
        yield mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.octoprint.async_setup_entry", return_value=None
    ) as mock:
        yield mock


@pytest.mark.usefixtures("mock_discovery_info", "mock_setup_entry")
async def test_import_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a YAML printer is imported and raises a deprecation issue."""
    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].unique_id == "uuid"
    assert entries[0].data == YAML_CONFIG[DOMAIN]
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "OctoPrint",
    }


@pytest.mark.usefixtures("mock_discovery_info", "mock_setup_entry")
async def test_import_yaml_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an already imported YAML printer still raises a deprecation issue."""
    MockConfigEntry(domain=DOMAIN, unique_id="uuid").add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(ApiError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_import_yaml_failed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_info: AsyncMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test a failed YAML import raises an import issue."""
    mock_discovery_info.side_effect = side_effect

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_yaml_already_configured_offline(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_info: AsyncMock,
) -> None:
    """Test an imported printer that is offline still raises a deprecation issue."""
    MockConfigEntry(
        domain=DOMAIN, unique_id="uuid", data=YAML_CONFIG[DOMAIN]
    ).add_to_hass(hass)
    mock_discovery_info.side_effect = ApiError

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    mock_discovery_info.assert_not_called()
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert len(issue_registry.issues) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_yaml_partial_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_discovery_info: AsyncMock,
) -> None:
    """Test a failed printer import prevents the remove-your-YAML issue."""
    mock_discovery_info.side_effect = [
        DiscoverySettings({"upnpUuid": "uuid"}),
        ApiError,
    ]
    config = {
        DOMAIN: [
            YAML_CONFIG[DOMAIN],
            {**YAML_CONFIG[DOMAIN], "host": "2.2.2.2", "name": "Second printer"},
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert len(issue_registry.issues) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_yaml_finishes_before_setup_returns(
    hass: HomeAssistant, mock_discovery_info: AsyncMock
) -> None:
    """Test all YAML printers are imported before the integration setup returns."""
    await translation.async_load_integrations(hass, {DOMAIN})
    mock_discovery_info.side_effect = [
        DiscoverySettings({"upnpUuid": "uuid"}),
        DiscoverySettings({"upnpUuid": "uuid2"}),
    ]
    config = {
        DOMAIN: [
            YAML_CONFIG[DOMAIN],
            {**YAML_CONFIG[DOMAIN], "host": "2.2.2.2", "name": "Second printer"},
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
