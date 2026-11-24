"""Test Anglian Water init."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyanglianwater.exceptions import (
    ConsentRequiredError,
    ExpiredAccessTokenError,
    HourlyReadingsUnavailableError,
    InteractionRequiredError,
    InvalidGrantError,
    SelfAssertedError,
    SmartMeterUnavailableError,
    UnknownEndpointError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.anglian_water.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONSENT_REQUIRED_ISSUE_ID

LATEST_READING_ENTITY_ID = "sensor.testsn_latest_reading"


@pytest.mark.usefixtures(
    "recorder_mock", "mock_anglian_water_client", "mock_anglian_water_authenticator"
)
async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of the config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception_type", "expected_state"),
    [
        pytest.param(
            ExpiredAccessTokenError,
            ConfigEntryState.SETUP_ERROR,
            id="expired_access_token",
        ),
        pytest.param(
            InteractionRequiredError,
            ConfigEntryState.SETUP_ERROR,
            id="interaction_required",
        ),
        pytest.param(
            InvalidGrantError,
            ConfigEntryState.SETUP_ERROR,
            id="invalid_grant",
        ),
        pytest.param(
            SelfAssertedError,
            ConfigEntryState.SETUP_ERROR,
            id="self_asserted",
        ),
    ],
)
@pytest.mark.usefixtures("mock_anglian_water_client")
async def test_setup_auth_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: MagicMock,
    exception_type: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure due to authentication errors."""
    mock_anglian_water_authenticator.send_refresh_request.side_effect = exception_type

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("recorder_mock", "mock_anglian_water_client")
async def test_setup_consent_required(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady and creates a repair issue when consent is required."""
    mock_anglian_water_authenticator.send_refresh_request.side_effect = (
        ConsentRequiredError
    )

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    issue = issue_registry.async_get_issue(DOMAIN, CONSENT_REQUIRED_ISSUE_ID)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id

    # Test that the issue is deleted once consent is granted
    mock_anglian_water_authenticator.send_refresh_request.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, CONSENT_REQUIRED_ISSUE_ID) is None


@pytest.mark.usefixtures("recorder_mock", "mock_anglian_water_client")
async def test_consent_required_issue_removed_with_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: MagicMock,
) -> None:
    """Test the consent required issue is removed with the config entry."""
    mock_anglian_water_authenticator.send_refresh_request.side_effect = (
        ConsentRequiredError
    )
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, CONSENT_REQUIRED_ISSUE_ID) is not None

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, CONSENT_REQUIRED_ISSUE_ID) is None


@pytest.mark.usefixtures("mock_anglian_water_authenticator")
async def test_setup_smart_meter_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test setup fails when the smart meter is unavailable."""
    mock_anglian_water_client.validate_smart_meter.side_effect = (
        SmartMeterUnavailableError
    )

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("recorder_mock")
async def test_setup_hourly_readings_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test setup fails with a translated error when hourly readings are unavailable."""
    mock_anglian_water_client.update.side_effect = HourlyReadingsUnavailableError(
        status=500, response="mock"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert (
        mock_config_entry.error_reason_translation_key == "hourly_readings_unavailable"
    )


@pytest.mark.parametrize(
    ("side_effect", "exception_type", "translation_key", "retry_after"),
    [
        pytest.param(
            UnknownEndpointError(status=500, response="Service Unavailable"),
            UpdateFailed,
            "service_unavailable",
            60.0,
            id="service_unavailable",
        ),
        pytest.param(
            ConsentRequiredError(),
            UpdateFailed,
            "consent_required",
            900.0,
            id="consent_required",
        ),
        pytest.param(
            ExpiredAccessTokenError(),
            ConfigEntryAuthFailed,
            "auth_expired",
            None,
            id="expired_access_token",
        ),
        pytest.param(
            InvalidGrantError(),
            ConfigEntryAuthFailed,
            "auth_expired",
            None,
            id="invalid_grant",
        ),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_update_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
    exception_type: type[HomeAssistantError],
    translation_key: str,
    retry_after: float | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update errors retain translated exceptions and make sensors unavailable."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(LATEST_READING_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED

    caplog.clear()
    mock_anglian_water_client.update.side_effect = side_effect

    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(LATEST_READING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED

    errors = [
        record.exc_info[1]
        for record in caplog.records
        if record.name == "homeassistant.components.anglian_water.coordinator"
        and record.exc_info is not None
    ]
    assert len(errors) == 1
    error = errors[0]
    assert isinstance(error, exception_type)
    assert error.translation_domain == DOMAIN
    assert error.translation_key == translation_key
    assert getattr(error, "retry_after", None) == retry_after


@pytest.mark.parametrize(
    ("side_effect", "retry_after"),
    [
        pytest.param(
            UnknownEndpointError(status=500, response="Service Unavailable"),
            60,
            id="service_unavailable",
        ),
        pytest.param(ConsentRequiredError(), 900, id="consent_required"),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_update_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
    retry_after: int,
) -> None:
    """Test transient failures retry automatically after the requested delay."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_anglian_water_client.update.side_effect = side_effect
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(LATEST_READING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_anglian_water_client.update.side_effect = None
    freezer.tick(timedelta(seconds=retry_after - 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(LATEST_READING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(LATEST_READING_ENTITY_ID)
    assert state is not None
    assert state.state == "50.0"
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(ExpiredAccessTokenError(), id="expired_access_token"),
        pytest.param(InvalidGrantError(), id="invalid_grant"),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_update_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Test authentication failures during polling start reauthentication."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.flow.async_progress() == []

    mock_anglian_water_client.update.side_effect = side_effect
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["handler"] == DOMAIN
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("side_effect", "issue_id", "translation_key", "retry_after"),
    [
        pytest.param(
            ConsentRequiredError(),
            CONSENT_REQUIRED_ISSUE_ID,
            "consent_required",
            900,
            id="consent_required",
        ),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_update_issues(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
    issue_id: str,
    translation_key: str,
    retry_after: int,
) -> None:
    """Test update failures create repair issues and clear them after recovery."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    mock_anglian_water_client.update.side_effect = side_effect
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.translation_key == translation_key
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_anglian_water_client.update.side_effect = None
    freezer.tick(timedelta(seconds=retry_after - 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert mock_config_entry.state is ConfigEntryState.LOADED
