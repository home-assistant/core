"""Test the Splunk integration init."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError

from homeassistant.components.splunk.const import CONF_FILTER, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_TOKEN
from homeassistant.core import HomeAssistant
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


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with connection error results in retry state."""
    mock_config_entry.add_to_hass(hass)

    mock_hass_splunk.check.return_value = False

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with auth error results in setup error state."""
    mock_config_entry.add_to_hass(hass)

    # Connectivity ok, but token check fails
    mock_hass_splunk.check.side_effect = [True, False]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_client_connection_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with ClientConnectionError results in retry state."""
    mock_config_entry.add_to_hass(hass)

    mock_hass_splunk.check.side_effect = ClientConnectionError("Connection failed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_timeout_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with timeout results in retry state."""
    mock_config_entry.add_to_hass(hass)

    mock_hass_splunk.check.side_effect = TimeoutError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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


async def test_yaml_import_without_filter(hass: HomeAssistant) -> None:
    """Test YAML configuration without filter triggers import."""
    with (
        patch(
            "homeassistant.components.splunk.hass_splunk", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.splunk.config_flow.hass_splunk", autospec=True
        ) as mock_config_flow_client_class,
        patch("homeassistant.components.splunk.async_setup_entry", return_value=True),
    ):
        mock_client = MagicMock()
        mock_client.check = AsyncMock(return_value=True)
        mock_client.queue = AsyncMock()

        mock_client_class.return_value = mock_client
        mock_config_flow_client_class.return_value = mock_client

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

    # Verify repair issue was created for deprecated YAML
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"

    # Verify import flow was triggered
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT


async def test_yaml_with_filter(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test YAML configuration with filter continues using YAML setup."""
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

    # Verify repair issue was created for deprecated YAML with filter
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_with_filter")
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_with_filter"

    # Verify no config entry was created (using YAML setup instead)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0

    # Verify event listener was set up
    assert mock_hass_splunk.check.call_count == 1
    assert mock_hass_splunk.queue.call_count == 1


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


async def test_event_listener_connection_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test event listener handles connection errors gracefully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a real state first
    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    # Simulate connection error when sending event
    mock_hass_splunk.queue.side_effect = ClientConnectionError("Connection failed")

    # Change the state to trigger an event - should not raise
    hass.states.async_set("sensor.test", "456")
    await hass.async_block_till_done()


async def test_event_listener_timeout(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test event listener handles timeouts gracefully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a real state first
    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    # Simulate timeout when sending event
    mock_hass_splunk.queue.side_effect = TimeoutError()

    # Change the state to trigger an event - should not raise
    hass.states.async_set("sensor.test", "456")
    await hass.async_block_till_done()


async def test_event_listener_response_error(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test event listener handles response errors gracefully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a real state first
    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    # Simulate response error when sending event
    mock_hass_splunk.queue.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Internal Server Error",
    )

    # Change the state to trigger an event - should not raise
    hass.states.async_set("sensor.test", "456")
    await hass.async_block_till_done()
