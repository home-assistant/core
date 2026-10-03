"""Tests for the arris_tg2492lg integration."""

from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
from arris_tg2492lg.exception import InvalidCredentialError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.arris_tg2492lg.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PLATFORM,
    STATE_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import http_error

from tests.common import MockConfigEntry, async_fire_time_changed

YAML_CONFIG = {
    DEVICE_TRACKER_DOMAIN: {
        CONF_PLATFORM: DOMAIN,
        CONF_PASSWORD: "password",
    }
}

LOGIN_ERRORS: list[tuple[Exception, ConfigEntryState]] = [
    (http_error(401), ConfigEntryState.SETUP_ERROR),
    (InvalidCredentialError(), ConfigEntryState.SETUP_ERROR),
]

REFRESH_CONNECTION_ERRORS: list[Exception] = [
    ClientConnectionError(),
    http_error(500),
    TimeoutError(),
]

REFRESH_AUTH_ERRORS: list[Exception] = [
    http_error(401),
    InvalidCredentialError(),
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


SETUP_CONNECTION_ERRORS: list[Exception] = [
    ClientConnectionError(),
    http_error(500),
    TimeoutError(),
]


@pytest.mark.usefixtures("mock_connect_box")
@pytest.mark.parametrize(
    "error",
    SETUP_CONNECTION_ERRORS,
    ids=["connection_error", "http_500", "timeout"],
)
async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    error: Exception,
) -> None:
    """Test setup fails with ConfigEntryNotReady on connection error."""
    mock_connect_box.async_login.side_effect = error

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_connect_box")
@pytest.mark.parametrize(
    "error",
    REFRESH_CONNECTION_ERRORS,
    ids=["connection_error", "http_500", "timeout"],
)
async def test_refresh_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test a refresh failure keeps the entry loaded and marks entities unavailable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME

    mock_connect_box.async_get_connected_devices.side_effect = error
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_connect_box")
@pytest.mark.parametrize(
    "error",
    REFRESH_AUTH_ERRORS,
    ids=["http_401", "invalid_credential"],
)
async def test_refresh_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_box: MagicMock,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test a refresh auth failure keeps the entry loaded and starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_connect_box.async_get_connected_devices.side_effect = error
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_connect_box", "mock_device_tracker_conf")
async def test_yaml_import_tracks_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Trackers for YAML-imported entries are enabled by default, like the legacy scanner."""
    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert {entity_entry.unique_id for entity_entry in entity_entries} == {
        f"{entry.entry_id}_AA:BB:CC:DD:EE:FF",
        f"{entry.entry_id}_11:22:33:44:55:66",
    }
    assert all(entity_entry.disabled_by is None for entity_entry in entity_entries)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_HOME


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
    mock_connect_box.async_login.side_effect = http_error(401)

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_invalid_auth")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.178.1"}
