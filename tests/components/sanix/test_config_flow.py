"""Define tests for the Sanix config flow."""

from unittest.mock import MagicMock

import pytest
from sanix.exceptions import SanixException, SanixInvalidAuthException

from homeassistant.components.sanix.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {CONF_SERIAL_NUMBER: "1810088", CONF_TOKEN: "75868dcf8ea4c64e2063f6c4e70132d2"}


async def test_create_entry(
    hass: HomeAssistant, mock_sanix: MagicMock, mock_setup_entry
) -> None:
    """Test that the user step works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MANUFACTURER
    assert result["data"] == {
        CONF_SERIAL_NUMBER: "1810088",
        CONF_TOKEN: "75868dcf8ea4c64e2063f6c4e70132d2",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SanixInvalidAuthException("Invalid auth"), "invalid_auth"),
        (SanixException("Something went wrong"), "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_sanix: MagicMock,
    mock_setup_entry,
) -> None:
    """Test Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_sanix.return_value.fetch_data.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG,
    )

    mock_sanix.return_value.fetch_data.side_effect = None

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sanix"
    assert result["data"] == {
        CONF_SERIAL_NUMBER: "1810088",
        CONF_TOKEN: "75868dcf8ea4c64e2063f6c4e70132d2",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_error(
    hass: HomeAssistant, mock_sanix: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
