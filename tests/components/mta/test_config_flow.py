"""Test the MTA config flow."""

from unittest.mock import AsyncMock, MagicMock

from pymta import MTAFeedError

from homeassistant.components.mta.const import (
    CONF_LINE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_subway_feed: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the complete config flow."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Select line
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LINE: "1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    assert result["errors"] == {}

    # Select stop and complete
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127N"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1 Line - Times Sq - 42 St (N direction)"
    assert result["data"] == {
        CONF_LINE: "1",
        CONF_STOP_ID: "127N",
        CONF_STOP_NAME: "Times Sq - 42 St (N direction)",
    }
    assert result["result"].unique_id == "1_127N"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_subway_feed: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127N"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_connection_error(
    hass: HomeAssistant,
    mock_subway_feed: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle connection errors and can recover."""
    mock_instance = mock_subway_feed.return_value
    mock_instance.get_arrivals.side_effect = MTAFeedError("Connection error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127S"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test recovery - reset mock to succeed
    mock_instance.get_arrivals.side_effect = None
    mock_instance.get_arrivals.return_value = []

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STOP_ID: "127S"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_get_stops(
    hass: HomeAssistant, mock_subway_feed: MagicMock
) -> None:
    """Test we abort when we cannot get stops."""
    mock_instance = mock_subway_feed.return_value
    mock_instance.get_stops.side_effect = MTAFeedError("Feed error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_form_no_stops_found(
    hass: HomeAssistant, mock_subway_feed: MagicMock
) -> None:
    """Test we abort when no stops are found."""
    mock_instance = mock_subway_feed.return_value
    mock_instance.get_stops.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_stops"
