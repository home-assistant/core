"""Tests for the Flipper IR config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.flipper_ir.const import (
    CONF_COMMANDS,
    CONF_IR_FILE,
    DOMAIN,
)
from homeassistant.components.flipper_ir.parser import InvalidIRFileError
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant, mock_process_uploaded_file: MagicMock
) -> None:
    """Test the full user flow creates an entry with parsed commands."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flipper_ir.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room TV",
                CONF_IR_FILE: mock_process_uploaded_file.file_id,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Living Room TV"
    assert result2["data"][CONF_NAME] == "Living Room TV"
    assert [c["name"] for c in result2["data"][CONF_COMMANDS]] == [
        "Power",
        "Vol_up",
        "Vol_down",
    ]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("mock_ir_content", [b"not-a-valid-ir-file"])
async def test_invalid_ir_file(
    hass: HomeAssistant, mock_process_uploaded_file: MagicMock
) -> None:
    """Test that an invalid IR file shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Living Room TV",
            CONF_IR_FILE: mock_process_uploaded_file.file_id,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_IR_FILE: "invalid_ir_file"}


async def test_recover_after_invalid_file(
    hass: HomeAssistant, mock_process_uploaded_file: MagicMock
) -> None:
    """The form is re-shown after an invalid file and can proceed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flipper_ir.config_flow.parse_ir_file",
        side_effect=[
            InvalidIRFileError("nope"),
            [{"name": "Power", "type": "parsed"}],
        ],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Bedroom",
                CONF_IR_FILE: mock_process_uploaded_file.file_id,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {CONF_IR_FILE: "invalid_ir_file"}

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Bedroom",
                CONF_IR_FILE: mock_process_uploaded_file.file_id,
            },
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Bedroom"
