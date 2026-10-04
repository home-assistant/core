"""Tests for the xiaomi integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.xiaomi.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.xiaomi.router import (
    XiaomiAuthError,
    XiaomiConnectionError,
    XiaomiTimeoutError,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
    STATE_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed

YAML_CONFIG = {
    DEVICE_TRACKER_DOMAIN: {
        CONF_PLATFORM: DOMAIN,
        CONF_HOST: "192.168.31.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
    }
}

MULTI_YAML_CONFIG = {
    DEVICE_TRACKER_DOMAIN: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: "192.168.31.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        {
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: "192.168.31.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    ]
}

CONNECTION_ERRORS: list[Exception] = [
    XiaomiConnectionError(),
    XiaomiTimeoutError(),
]


@pytest.mark.usefixtures("mock_xiaomi_client")
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


@pytest.mark.usefixtures("mock_xiaomi_client")
@pytest.mark.parametrize(
    "error",
    CONNECTION_ERRORS,
    ids=["connection_error", "timeout"],
)
async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
    error: Exception,
) -> None:
    """Test setup fails with ConfigEntryNotReady on connection error."""
    mock_xiaomi_client.login.side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_xiaomi_client")
@pytest.mark.parametrize(
    "error",
    CONNECTION_ERRORS,
    ids=["connection_error", "timeout"],
)
async def test_setup_entry_first_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
    error: Exception,
) -> None:
    """Test a failed first refresh after a successful login retries setup."""
    mock_xiaomi_client.login.return_value = "token"
    mock_xiaomi_client.get_device_list.side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
) -> None:
    """Test setup fails with ConfigEntryAuthFailed and starts a reauth flow."""
    mock_xiaomi_client.login.side_effect = XiaomiAuthError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_xiaomi_client")
@pytest.mark.parametrize(
    "error",
    CONNECTION_ERRORS,
    ids=["connection_error", "timeout"],
)
async def test_refresh_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
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

    mock_xiaomi_client.get_device_list.side_effect = error
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.my_phone")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_xiaomi_client")
async def test_refresh_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a refresh auth failure keeps the entry loaded and starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_xiaomi_client.get_device_list.side_effect = XiaomiAuthError()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_xiaomi_client", "mock_device_tracker_conf")
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
    assert entries[0].data[CONF_USERNAME] == "admin"
    assert entries[0].data[CONF_PASSWORD] == "password"

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_device_tracker_yaml_192.168.31.1"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {"host": "192.168.31.1"}


@pytest.mark.usefixtures("mock_device_tracker_conf")
@pytest.mark.parametrize(
    "error",
    [XiaomiConnectionError(), XiaomiTimeoutError()],
    ids=["connection_error", "timeout"],
)
async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    mock_xiaomi_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    error: Exception,
) -> None:
    """Test importing YAML config creates an issue on connection failure."""
    mock_xiaomi_client.login.side_effect = error

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(
        DOMAIN, "yaml_import_cannot_connect_192.168.31.1"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.31.1"}


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_invalid_auth(
    hass: HomeAssistant,
    mock_xiaomi_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on invalid auth."""
    mock_xiaomi_client.login.side_effect = XiaomiAuthError()

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    issue = issue_registry.async_get_issue(
        DOMAIN, "yaml_import_invalid_auth_192.168.31.1"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.31.1"}


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_multiple_cannot_connect(
    hass: HomeAssistant,
    mock_xiaomi_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each failing YAML import creates its own issue keyed by host."""
    mock_xiaomi_client.login.side_effect = XiaomiConnectionError()

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, MULTI_YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    for host in ("192.168.31.1", "192.168.31.2"):
        issue = issue_registry.async_get_issue(
            DOMAIN, f"yaml_import_cannot_connect_{host}"
        )
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.ERROR
        assert issue.translation_placeholders == {"host": host}
