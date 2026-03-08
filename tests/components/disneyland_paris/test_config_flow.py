"""Test the Disneyland Paris config flow."""

from unittest.mock import AsyncMock

from dlpwait import DLPWaitError

from homeassistant.components.disneyland_paris.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_async_step_user_gets_form_and_creates_entry(
    hass: HomeAssistant,
    mock_disneyland_paris_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that the we can view the form and that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that we abort if we attempt to submit the same entry twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_successful_recovery_after_connection_error(
    hass: HomeAssistant,
    mock_disneyland_paris_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error is shown when connection fails, and configuration succeeds after retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Simulate a connection error by raising a DLPWaitError
    mock_disneyland_paris_client.update.side_effect = DLPWaitError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Simulate successful connection on retry
    mock_disneyland_paris_client.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
