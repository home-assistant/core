"""Test the Splunk integration init."""

from http import HTTPStatus
import logging
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError, ClientResponseError
from hass_splunk import SplunkPayloadError
import pytest

from homeassistant.components.splunk.const import CONF_FILTER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

YAML_FILTER = {"include_domains": ["sensor"]}


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
    ("side_effect", "expected_state", "expected_error_key"),
    [
        ([False, False], ConfigEntryState.SETUP_RETRY, "cannot_connect"),
        (
            ClientConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
        ),
        (TimeoutError(), ConfigEntryState.SETUP_RETRY, "timeout_connect"),
        (
            Exception("Unexpected error"),
            ConfigEntryState.SETUP_RETRY,
            "unexpected_connect_error",
        ),
        ([True, False], ConfigEntryState.SETUP_ERROR, "invalid_auth"),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception | list[bool],
    expected_state: ConfigEntryState,
    expected_error_key: str,
) -> None:
    """Test setup with various errors results in appropriate states."""
    mock_config_entry.add_to_hass(hass)

    mock_hass_splunk.check.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_key == expected_error_key


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


async def test_setup_without_yaml(
    hass: HomeAssistant, mock_hass_splunk: AsyncMock
) -> None:
    """Test setup without YAML succeeds."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "yaml_config",
    [
        pytest.param({CONF_FILTER: YAML_FILTER}, id="filter_only"),
        pytest.param(
            {
                CONF_TOKEN: "yaml-token",
                CONF_HOST: "yaml-host",
                CONF_PORT: 8089,
                CONF_SSL: False,
                CONF_FILTER: YAML_FILTER,
            },
            id="with_removed_connection_settings",
        ),
    ],
)
async def test_event_listener_with_filter(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    yaml_config: ConfigType,
) -> None:
    """Test event listener respects entity filter from YAML."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: yaml_config})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Reset queue call count after startup event
    mock_hass_splunk.queue.reset_mock()

    hass.states.async_set("sensor.test", "123")
    await hass.async_block_till_done()

    assert mock_hass_splunk.queue.call_count == 1

    mock_hass_splunk.queue.reset_mock()

    hass.states.async_set("light.test", "on")
    await hass.async_block_till_done()

    assert mock_hass_splunk.queue.call_count == 0


async def test_yaml_connection_settings_not_imported(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test YAML connection settings are ignored and no config entry is created."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_TOKEN: "yaml-token",
                CONF_HOST: "yaml-host",
                CONF_PORT: 8089,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert (
        "The 'token' option has been removed, please remove it from your configuration"
        in caplog.text
    )


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
        (
            SplunkPayloadError(0, "Bad request", HTTPStatus.BAD_REQUEST),
            logging.WARNING,
            "Splunk payload error: Bad request",
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


@pytest.mark.parametrize(
    ("error", "expected_log_level", "expected_message", "expected_traceback"),
    [
        (
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            ),
            logging.WARNING,
            "Splunk response error: Internal Server Error",
            False,
        ),
        (
            SplunkPayloadError(0, "Unauthorized", HTTPStatus.UNAUTHORIZED),
            logging.ERROR,
            "Splunk token unauthorized",
            False,
        ),
        (
            ValueError("boom"),
            logging.ERROR,
            "Unexpected error sending event to Splunk",
            True,
        ),
    ],
)
async def test_event_listener_repeated_failures_log_at_debug(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    expected_log_level: int,
    expected_message: str,
    expected_traceback: bool,
) -> None:
    """Test the first failure logs at its level and the repeats log at debug."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_hass_splunk.queue.side_effect = error

    with caplog.at_level(logging.DEBUG):
        for i in range(5):
            hass.states.async_set("sensor.test", str(i))
            await hass.async_block_till_done()

    matching_records = [
        record for record in caplog.records if expected_message in record.message
    ]
    assert len(matching_records) == 5
    assert matching_records[0].levelno == expected_log_level
    # A traceback is worth one record per outage, never one per state change.
    assert bool(matching_records[0].exc_info) is expected_traceback
    assert all(record.levelno == logging.DEBUG for record in matching_records[1:])
    assert not any(record.exc_info for record in matching_records[1:])


@pytest.mark.parametrize(
    ("first_error", "first_message", "first_level", "second_error", "second_message"),
    [
        pytest.param(
            ClientConnectionError("Connection failed"),
            "Connection error sending to Splunk",
            logging.DEBUG,
            SplunkPayloadError(0, "Unauthorized", HTTPStatus.UNAUTHORIZED),
            "Splunk token unauthorized",
            id="more_severe_second_failure",
        ),
        pytest.param(
            SplunkPayloadError(0, "Unauthorized", HTTPStatus.UNAUTHORIZED),
            "Splunk token unauthorized",
            logging.ERROR,
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            ),
            "Splunk response error: Internal Server Error",
            id="less_severe_second_failure",
        ),
    ],
)
async def test_event_listener_different_failure_during_outage_logs_at_debug(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    first_error: Exception,
    first_message: str,
    first_level: int,
    second_error: Exception,
    second_message: str,
) -> None:
    """Test a different failure during an outage logs at debug, whatever its level."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with caplog.at_level(logging.DEBUG):
        mock_hass_splunk.queue.side_effect = first_error
        hass.states.async_set("sensor.test", "outage")
        await hass.async_block_till_done()

        mock_hass_splunk.queue.side_effect = second_error
        for i in range(2):
            hass.states.async_set("sensor.test", f"different-{i}")
            await hass.async_block_till_done()

    first_records = [
        record for record in caplog.records if first_message in record.message
    ]
    assert len(first_records) == 1
    assert first_records[0].levelno == first_level

    second_records = [
        record for record in caplog.records if second_message in record.message
    ]
    assert len(second_records) == 2
    assert all(record.levelno == logging.DEBUG for record in second_records)


async def test_event_listener_recovery_logs_once_at_info(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a recovered outage logs a single info record."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_hass_splunk.queue.side_effect = ClientConnectionError("Connection failed")

    with caplog.at_level(logging.DEBUG):
        for i in range(2):
            hass.states.async_set("sensor.test", str(i))
            await hass.async_block_till_done()

        mock_hass_splunk.queue.side_effect = None
        for i in range(2):
            hass.states.async_set("sensor.test", f"recovered-{i}")
            await hass.async_block_till_done()

    recovery_records = [
        record
        for record in caplog.records
        if "Sending events to Splunk has recovered" in record.message
    ]
    assert len(recovery_records) == 1
    assert recovery_records[0].levelno == logging.INFO


async def test_event_listener_failure_after_recovery_logs_at_natural_level(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a new outage after a recovery logs at its natural level again."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_hass_splunk.queue.side_effect = ClientConnectionError("Connection failed")

    with caplog.at_level(logging.DEBUG):
        hass.states.async_set("sensor.test", "first-outage")
        await hass.async_block_till_done()

        mock_hass_splunk.queue.side_effect = None
        hass.states.async_set("sensor.test", "recovered")
        await hass.async_block_till_done()

        caplog.clear()
        mock_hass_splunk.queue.side_effect = ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Internal Server Error",
        )
        hass.states.async_set("sensor.test", "second-outage")
        await hass.async_block_till_done()

    assert any(
        record.levelno == logging.WARNING
        and "Splunk response error: Internal Server Error" in record.message
        for record in caplog.records
    )


async def test_event_listener_coalesced_send_is_not_a_recovery(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a send coalesced into an in-flight send isn't treated as success.

    hass_splunk.queue() returns False, without raising, when a send is already
    in flight, which says nothing about whether this event reached Splunk.
    """
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    error = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Internal Server Error",
    )
    mock_hass_splunk.queue.side_effect = [error, False, error]

    with caplog.at_level(logging.DEBUG):
        for i in range(3):
            hass.states.async_set("sensor.test", str(i))
            await hass.async_block_till_done()

    assert not any(
        "Sending events to Splunk has recovered" in record.message
        for record in caplog.records
    )

    # Still demoted, so the coalesced send did not clear the outage either.
    failure_records = [
        record
        for record in caplog.records
        if "Splunk response error: Internal Server Error" in record.message
    ]
    assert len(failure_records) == 2
    assert failure_records[0].levelno == logging.WARNING
    assert failure_records[1].levelno == logging.DEBUG


async def test_event_listener_no_recovery_message_without_prior_failure(
    hass: HomeAssistant,
    mock_hass_splunk: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a successful send without prior failures logs no recovery message."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with caplog.at_level(logging.DEBUG):
        hass.states.async_set("sensor.test", "123")
        await hass.async_block_till_done()

    assert not any(
        "Sending events to Splunk has recovered" in record.message
        for record in caplog.records
    )
