"""Test the Sense config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sense_energy import (
    SenseAPIException,
    SenseAPITimeoutException,
    SenseAuthenticationException,
    SenseMFARequiredException,
    SenseWebsocketException,
)

from homeassistant import config_entries
from homeassistant.components.sense.const import DOMAIN
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_flow_sense")
def mock_flow_sense_fixture() -> Generator[MagicMock]:
    """Mock Sense object for authentication."""
    with patch(
        "homeassistant.components.sense.config_flow.ASyncSenseable"
    ) as mock_sense:
        mock_sense.return_value.authenticate = AsyncMock(return_value=True)
        mock_sense.return_value.validate_mfa = AsyncMock(return_value=True)
        mock_sense.return_value.sense_access_token = "ABC"
        mock_sense.return_value.sense_user_id = "123"
        mock_sense.return_value.sense_monitor_id = "456"
        mock_sense.return_value.device_id = "789"
        mock_sense.return_value.refresh_token = "XYZ"
        yield mock_sense


async def test_form(
    hass: HomeAssistant,
    mock_flow_sense: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"timeout": "6", "email": "test-email", "password": "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SenseAuthenticationException, "invalid_auth"),
        (SenseAPITimeoutException, "cannot_connect"),
        (SenseAPIException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_flow_sense: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test we handle all exceptions in the user flow and can recover."""
    mock_flow_sense.return_value.authenticate.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"timeout": "6", "email": "test-email", "password": "test-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Verify recovery: clear the error and complete the flow successfully
    mock_flow_sense.return_value.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"timeout": "6", "email": "test-email", "password": "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_mfa_required(
    hass: HomeAssistant,
    mock_flow_sense: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle the MFA flow."""
    mock_flow_sense.return_value.authenticate.side_effect = SenseMFARequiredException

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"timeout": "6", "email": "test-email", "password": "test-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "validation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CODE: "012345"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == MOCK_CONFIG


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SenseAuthenticationException, "invalid_auth"),
        (SenseAPITimeoutException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_mfa_exceptions(
    hass: HomeAssistant,
    mock_flow_sense: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test we handle all MFA validation exceptions and can recover."""
    mock_flow_sense.return_value.authenticate.side_effect = SenseMFARequiredException

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"timeout": "6", "email": "test-email", "password": "test-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "validation"

    mock_flow_sense.return_value.validate_mfa.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CODE: "000000"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert result["step_id"] == "validation"

    # Verify recovery: clear the error and complete MFA successfully
    mock_flow_sense.return_value.validate_mfa.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CODE: "012345"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == MOCK_CONFIG


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPITimeoutException,
        SenseAPIException,
        SenseWebsocketException,
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Test we handle exceptions during async_setup_entry and can recover."""
    mock_sense.update_realtime.side_effect = exception
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY

    # Verify recovery: clear the error and reload the entry
    mock_sense.update_realtime.side_effect = None
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED


async def test_reauth_no_form(
    hass: HomeAssistant,
    mock_flow_sense: MagicMock,
) -> None:
    """Test reauth where no form needed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="test-email",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=True,
    ):
        result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_password(
    hass: HomeAssistant,
    mock_flow_sense: MagicMock,
) -> None:
    """Test reauth form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="test-email",
    )
    entry.add_to_hass(hass)
    mock_flow_sense.return_value.authenticate.side_effect = SenseAuthenticationException

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    mock_flow_sense.return_value.authenticate.side_effect = None
    with patch(
        "homeassistant.components.sense.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
