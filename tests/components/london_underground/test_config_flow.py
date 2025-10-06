"""Test the London Underground config flow."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.london_underground.const import (
    CONF_LINE,
    DEFAULT_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_validate_input_success(
    hass: HomeAssistant, mock_setup_entry, mock_london_underground_client
) -> None:
    """Test successful validation of TfL API."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: ["Bakerloo", "Central"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Underground"
    assert result["data"] == {}
    assert result["options"] == {CONF_LINE: ["Bakerloo", "Central"]}


async def test_options(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_LINE: DEFAULT_LINES},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LINE: ["Bakerloo", "Central"],
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LINE: ["Bakerloo", "Central"],
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (Exception, "cannot_connect"),
        (asyncio.TimeoutError, "timeout_connect"),
    ],
)
async def test_validate_input_exceptions(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_london_underground_client,
    side_effect,
    expected_error,
) -> None:
    """Test validation with connection and timeout errors."""

    mock_london_underground_client.update.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.london_underground.config_flow.async_get_clientsession"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LINE: ["Bakerloo", "Central"]},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # confirm recovery after error
    mock_london_underground_client.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Underground"
    assert result["data"] == {}
    assert result["options"] == {CONF_LINE: DEFAULT_LINES}
