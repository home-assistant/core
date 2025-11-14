"""Test the Saunum config flow."""

from __future__ import annotations

from pysaunum import SaunumConnectionError, SaunumException
import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {CONF_HOST: "192.168.1.100"}


@pytest.mark.usefixtures("mock_saunum_client")
async def test_full_flow(hass: HomeAssistant) -> None:
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
    assert result["title"] == "Saunum Leil Sauna"
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
    assert result["title"] == "Saunum Leil Sauna"
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
