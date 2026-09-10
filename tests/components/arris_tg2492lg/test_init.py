"""Tests for the arris_tg2492lg integration."""

from unittest.mock import MagicMock

from aiohttp import ClientConnectionError, ClientResponseError
from arris_tg2492lg.exception import InvalidCredentialError
import pytest

from homeassistant.components.arris_tg2492lg.const import DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

YAML_CONFIG = {
    DEVICE_TRACKER_DOMAIN: {
        CONF_PLATFORM: DOMAIN,
        CONF_PASSWORD: "password",
    }
}

LOGIN_ERRORS: list[tuple[Exception, ConfigEntryState]] = [
    (ClientResponseError(None, None, status=401), ConfigEntryState.SETUP_ERROR),
    (InvalidCredentialError(), ConfigEntryState.SETUP_ERROR),
]


@pytest.mark.usefixtures("mock_connect_box")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
) -> None:
    """Test setup fails with ConfigEntryNotReady on connection error."""
    mock_connect_box.async_login.side_effect = ClientConnectionError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("error", "state"),
    LOGIN_ERRORS,
    ids=["http_401", "invalid_credential"],
)
async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup fails with ConfigEntryAuthFailed and starts a reauth flow."""
    mock_connect_box.async_login.side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_connect_box", "mock_device_tracker_conf")
async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates a config entry and a deprecation issue."""
    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data[CONF_PASSWORD] == "password"

    issue = issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    mock_connect_box: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on connection failure."""
    mock_connect_box.async_login.side_effect = ClientConnectionError()

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.178.1"}


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_invalid_auth(
    hass: HomeAssistant,
    mock_connect_box: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on invalid auth."""
    mock_connect_box.async_login.side_effect = ClientResponseError(
        None, None, status=401
    )

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_invalid_auth")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.178.1"}
