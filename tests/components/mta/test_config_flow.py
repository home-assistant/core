"""Test the MTA config flow."""

from unittest.mock import AsyncMock, MagicMock

from pymta import MTAFeedError
import pytest

from homeassistant.components.mta.const import (
    CONF_LINE,
    CONF_ROUTE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_BUS,
    SUBENTRY_TYPE_SUBWAY,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_main_entry_flow_without_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the main config flow without API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MTA"
    assert result["data"] == {CONF_API_KEY: None}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_main_entry_flow_with_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_bus_feed: MagicMock,
) -> None:
    """Test the main config flow with API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test_api_key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MTA"
    assert result["data"] == {CONF_API_KEY: "test_api_key"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_main_entry_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if MTA is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (MTAFeedError("Connection error"), "cannot_connect"),
        (RuntimeError("Unexpected error"), "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bus_feed: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test the reauth flow with connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_bus_feed.return_value.get_stops.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad_api_key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_bus_feed.return_value.get_stops.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


# Subway subentry tests


async def test_subway_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test the subway subentry flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_SUBWAY),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LINE: "1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "127N"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1 - Times Sq - 42 St (N direction)"
    assert result["data"] == {
        CONF_LINE: "1",
        CONF_STOP_ID: "127N",
        CONF_STOP_NAME: "Times Sq - 42 St (N direction)",
    }


async def test_subway_subentry_already_configured(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test subway subentry already configured."""
    mock_config_entry_with_subway_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_subway_subentry.entry_id, SUBENTRY_TYPE_SUBWAY),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LINE: "1"}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "127N"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subway_subentry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test subway subentry flow with connection error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_subway_feed.return_value.get_arrivals.side_effect = MTAFeedError(
        "Connection error"
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_SUBWAY),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LINE: "1"}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "127N"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_subway_subentry_cannot_get_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test subway subentry flow when cannot get stops."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_subway_feed.return_value.get_stops.side_effect = MTAFeedError("Feed error")

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_SUBWAY),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LINE: "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_subway_subentry_no_stops_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_subway_feed: MagicMock,
) -> None:
    """Test subway subentry flow when no stops are found."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_subway_feed.return_value.get_stops.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_SUBWAY),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LINE: "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_stops"


# Bus subentry tests


async def test_bus_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry_with_api_key: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test the bus subentry flow."""
    mock_config_entry_with_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_api_key.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_api_key.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "M15 - 1 Av/E 79 St"
    assert result["data"] == {
        CONF_ROUTE: "M15",
        CONF_STOP_ID: "400561",
        CONF_STOP_NAME: "1 Av/E 79 St",
    }


async def test_bus_subentry_flow_without_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test the bus subentry flow without API token (space workaround)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bus_subentry_already_configured(
    hass: HomeAssistant,
    mock_config_entry_with_bus_subentry: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test bus subentry already configured."""
    mock_config_entry_with_bus_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_bus_subentry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_bus_subentry.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bus_subentry_invalid_route(
    hass: HomeAssistant,
    mock_config_entry_with_api_key: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test bus subentry flow with invalid route."""
    mock_config_entry_with_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_api_key.entry_id)
    await hass.async_block_till_done()

    mock_bus_feed.return_value.get_stops.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_api_key.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "INVALID"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_route"}


async def test_bus_subentry_route_fetch_error(
    hass: HomeAssistant,
    mock_config_entry_with_api_key: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test bus subentry flow when route fetch fails (treated as invalid route)."""
    mock_config_entry_with_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_api_key.entry_id)
    await hass.async_block_till_done()

    mock_bus_feed.return_value.get_stops.side_effect = MTAFeedError("Connection error")

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_api_key.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_route"}

    mock_bus_feed.return_value.get_stops.side_effect = None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bus_subentry_connection_test_error(
    hass: HomeAssistant,
    mock_config_entry_with_api_key: MockConfigEntry,
    mock_bus_feed: MagicMock,
) -> None:
    """Test bus subentry flow when connection test fails after route validation."""
    mock_config_entry_with_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_api_key.entry_id)
    await hass.async_block_till_done()

    # get_stops succeeds but get_arrivals fails
    mock_bus_feed.return_value.get_arrivals.side_effect = MTAFeedError(
        "Connection error"
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_api_key.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_bus_feed.return_value.get_arrivals.side_effect = None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bus_subentry_with_direction(
    hass: HomeAssistant,
    mock_config_entry_with_api_key: MockConfigEntry,
    mock_bus_feed_with_direction: MagicMock,
) -> None:
    """Test bus subentry flow shows direction for stops."""
    mock_config_entry_with_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_api_key.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_api_key.entry_id, SUBENTRY_TYPE_BUS),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE: "M15"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    # Select a stop with direction info
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP_ID: "400561"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Stop name should include direction
    assert result["title"] == "M15 - 1 Av/E 79 St (to South Ferry)"
    assert result["data"][CONF_STOP_NAME] == "1 Av/E 79 St (to South Ferry)"
