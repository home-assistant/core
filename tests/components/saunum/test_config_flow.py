"""Test the Saunum config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pysaunum import SaunumConnectionError, SaunumException
import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {CONF_HOST: "192.168.1.100"}
TEST_RECONFIGURE_INPUT = {CONF_HOST: "192.168.1.200"}


@pytest.mark.usefixtures("mock_saunum_client")
async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Saunum"
    assert result["data"] == TEST_USER_INPUT


@pytest.mark.parametrize(
    ("side_effect", "error_base"),
    [
        (SaunumConnectionError("Connection failed"), "cannot_connect"),
        (SaunumException("Read error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_saunum_client,
    side_effect: Exception,
    error_base: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error handling and recovery."""
    mock_saunum_client.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Test recovery - clear the error and try again
    mock_saunum_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Saunum"
    assert result["data"] == TEST_USER_INPUT


@pytest.mark.usefixtures("mock_saunum_client")
async def test_form_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate entry handling."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_saunum_client")
@pytest.mark.parametrize("user_input", [TEST_RECONFIGURE_INPUT, TEST_USER_INPUT])
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, str],
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == user_input


@pytest.mark.parametrize(
    ("side_effect", "error_base"),
    [
        (SaunumConnectionError("Connection failed"), "cannot_connect"),
        (SaunumException("Read error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    side_effect: Exception,
    error_base: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow error handling."""
    mock_config_entry.add_to_hass(hass)
    mock_saunum_client.connect.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_RECONFIGURE_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Test recovery - clear the error and try again
    mock_saunum_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_RECONFIGURE_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == TEST_RECONFIGURE_INPUT


@pytest.mark.usefixtures("mock_saunum_client")
async def test_reconfigure_to_existing_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure flow aborts when changing to a host used by another entry."""
    mock_config_entry.add_to_hass(hass)

    # Create a second entry with a different host
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_RECONFIGURE_INPUT,
        title="Saunum 2",
    )
    second_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    # Try to reconfigure first entry to use the same host as second entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_RECONFIGURE_INPUT,  # Same host as second_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the original entry was not changed
    assert mock_config_entry.data == TEST_USER_INPUT
