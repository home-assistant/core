"""Test the Splunk integration init."""

from http import HTTPStatus
import logging
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError
import pytest

from homeassistant.components.splunk.const import CONF_FILTER, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup from config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify client was created and checked
    assert mock_hass_splunk.check.call_count == 2
    # First call checks connectivity
    mock_hass_splunk.check.assert_any_call(connectivity=True, token=False, busy=False)
    # Second call checks token
    mock_hass_splunk.check.assert_any_call(connectivity=False, token=True, busy=False)

    # Verify startup event was queued
    assert mock_hass_splunk.queue.call_count == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        ([False, False], ConfigEntryState.SETUP_RETRY),
        (ClientConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
        (TimeoutError(), ConfigEntryState.SETUP_RETRY),
        ([True, False], ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception | list[bool],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup with various errors results in appropriate states."""
    mock_config_entry.add_to_hass(hass)

    mock_hass_splunk.check.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_yaml_import_without_filter(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test YAML configuration without filter triggers import."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "test-token",
                CONF_HOST: "localhost",
                CONF_PORT: 8088,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Verify import flow was triggered
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT


async def test_yaml_with_filter(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test YAML configuration with filter triggers import."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "test-token",
                CONF_HOST: "localhost",
                CONF_PORT: 8088,
                CONF_SSL: False,
                CONF_FILTER: {
                    "include_domains": ["sensor"],
                },
            }
        },
    )
    await hass.async_block_till_done()

    # Verify import flow was triggered
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT


async def test_setup_without_yaml(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test setup without YAML succeeds."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_event_listener_with_filter(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test event listener respects entity filter from YAML."""
    # Set up via YAML with a filter that only allows sensor entities
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "test-token",
                CONF_HOST: "localhost",
                CONF_PORT: 8088,
                CONF_SSL: False,
                CONF_FILTER: {
                    "include_domains": ["sensor"],
                },
            }
        },
    )
    await hass.async_block_till_done()

    # Verify config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    # Reset queue call count after startup event
    mock_hass_splunk.queue.reset_mock()

    # Create a sensor state (should be sent)
    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    # Verify event was sent for sensor
    assert mock_hass_splunk.queue.call_count == 1

    # Reset
    mock_hass_splunk.queue.reset_mock()

    # Create a light state (should be filtered out)
    hass.states.async_set("light.test", "on")
    await hass.async_block_till_done()

    # Verify no event was sent for light (filtered out)
    assert mock_hass_splunk.queue.call_count == 0


async def test_event_listener_unauthorized(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test event listener triggers reauth on unauthorized error."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a real state first
    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    # Simulate unauthorized error when sending event
    mock_hass_splunk.queue.side_effect = SplunkPayloadError(
        0, "Unauthorized", HTTPStatus.UNAUTHORIZED
    )

    # Change the state to trigger an event
    hass.states.async_set("sensor.test", "456")
    await hass.async_block_till_done()

    # Verify reauth flow was started
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.parametrize(
    ("error", "expected_log_level", "expected_message"),
    [
        (
            ClientConnectionError("Connection failed"),
            logging.DEBUG,
            "Connection error sending to Splunk",
        ),
        (
            TimeoutError(),
            logging.DEBUG,
            "Timeout sending to Splunk",
        ),
        (
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            ),
            logging.WARNING,
            "Splunk response error: Internal Server Error",
        ),
    ],
)
async def test_event_listener_error_handling(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    expected_log_level: int,
    expected_message: str,
) -> None:
    """Test event listener handles various errors gracefully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a real state first
    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    # Simulate error when sending event
    mock_hass_splunk.queue.side_effect = error

    # Change the state to trigger an event - should not raise
    with caplog.at_level(logging.DEBUG):
        hass.states.async_set("sensor.test", "456")
        await hass.async_block_till_done()

    assert any(
        record.levelno == expected_log_level and expected_message in record.message
        for record in caplog.records
    )


async def test_yaml_filter_only_no_deprecation_issue(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test YAML with only filter does not create deprecation issue."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                # Only filter, no connection settings (no token)
                CONF_FILTER: {
                    "include_domains": ["sensor"],
                },
            }
        },
    )
    await hass.async_block_till_done()

    # Verify no config entry was created (no import)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0

    # Verify no deprecation issue was created
    issue_registry = ir.async_get(hass)
    issues = issue_registry.issues
    assert not any(
        issue_id[0] == DOMAIN and "deprecated" in issue_id[1] for issue_id in issues
    )
    assert not any(
        issue_id[0] == HOMEASSISTANT_DOMAIN and DOMAIN in issue_id[1]
        for issue_id in issues
    )


async def test_yaml_with_connection_creates_deprecation_issue(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test YAML with connection settings creates deprecation issue."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "test-token",
                CONF_HOST: "localhost",
                CONF_PORT: 8088,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Verify import flow was triggered
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT

    # Verify deprecation issue was created in homeassistant domain
    issue_registry = ir.async_get(hass)
    assert (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}") in issue_registry.issues


async def test_yaml_import_error_creates_specific_issue(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test YAML import with connection error creates specific issue."""
    # Config flow client fails connectivity check
    mock_hass_splunk.check.return_value = False

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "test-token",
                CONF_HOST: "invalid-host",
                CONF_PORT: 8088,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Verify no config entry was created (import failed)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0

    # Verify error-specific issue was created
    issue_registry = ir.async_get(hass)
    assert (
        DOMAIN,
        "deprecated_yaml_import_issue_cannot_connect",
    ) in issue_registry.issues


async def test_yaml_import_already_configured_creates_deprecation_issue(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML import when already configured still creates deprecation issue."""
    # Add existing config entry before YAML import
    mock_config_entry.add_to_hass(hass)

    # Set up component with YAML - should see existing entry and abort with single_instance_allowed
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "test-token",
                CONF_HOST: "localhost",
                CONF_PORT: 8088,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Verify deprecation issue was still created (single_instance_allowed is ok)
    issue_registry = ir.async_get(hass)
    assert (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}") in issue_registry.issues
