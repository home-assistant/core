"""Test the OpenAQ config flow."""

from unittest.mock import AsyncMock

from openaq import (
    BadGatewayError,
    GatewayTimeoutError,
    HTTPRateLimitError,
    NotAuthorizedError,
    NotFoundError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.openaq.const import (
    CONF_LIMIT,
    CONF_LOCATION_ID,
    CONF_RADIUS,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LOCATION,
    ATTR_LONGITUDE,
    CONF_API_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, LOCATION_ID, make_location, make_response

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_openaq_client: AsyncMock
) -> None:
    """Test successful API key setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenAQ"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert result["result"].unique_id == DOMAIN
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NotAuthorizedError("Invalid API key"), "invalid_auth"),
        (GatewayTimeoutError("Timeout"), "cannot_connect"),
        (HTTPRateLimitError("Rate limited"), "rate_limited"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_openaq_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test API key setup errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_openaq_client.parameters.list.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_openaq_client.parameters.list.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_parent_entry(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate parent setup aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_API_KEY: "other-api-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_openaq_client.parameters.list.assert_not_awaited()


async def test_location_subentry_map_flow(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an OpenAQ location via map search."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response(
        [make_location(location_id=9999, name="South Valley")]
    )
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "map"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 35.1, ATTR_LONGITUDE: -106.6},
            CONF_RADIUS: 5000,
            CONF_LIMIT: 10,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: "9999"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "South Valley, Albuquerque"
    assert result["data"] == {CONF_LOCATION_ID: 9999}
    assert list(mock_config_entry.subentries.values())[1].unique_id == "9999"
    mock_openaq_client.locations.list.assert_awaited_once_with(
        coordinates=(35.1, -106.6),
        radius=5000,
        limit=10,
    )


async def test_location_subentry_no_locations_found(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search with no matching OpenAQ locations."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response([])
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "map"}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 35.1, ATTR_LONGITUDE: -106.6},
            CONF_RADIUS: 5000,
            CONF_LIMIT: 10,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["errors"] == {"base": "no_locations_found"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (HTTPRateLimitError("Rate limited"), "rate_limited"),
        (BadGatewayError("Bad gateway"), "cannot_connect"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_location_subentry_map_flow_errors(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test map search API errors."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.side_effect = exception
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "map"}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {ATTR_LATITUDE: 35.1, ATTR_LONGITUDE: -106.6},
            CONF_RADIUS: 5000,
            CONF_LIMIT: 10,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["errors"] == {"base": error}


async def test_location_subentry_location_id_flow(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an OpenAQ location by location ID."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": CONF_LOCATION_ID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_LOCATION_ID

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: 9999}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_LOCATION_ID: 9999}
    assert list(mock_config_entry.subentries.values())[1].unique_id == "9999"
    mock_openaq_client.locations.get.assert_awaited_once_with(9999)


async def test_location_subentry_location_id_not_found(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an invalid OpenAQ location ID."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.get.side_effect = NotFoundError("Location not found")
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": CONF_LOCATION_ID}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: 9999}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_LOCATION_ID
    assert result["errors"] == {"base": "invalid_location"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (HTTPRateLimitError("Rate limited"), "rate_limited"),
        (BadGatewayError("Bad gateway"), "cannot_connect"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_location_subentry_location_id_flow_errors(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test location ID API errors."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.get.side_effect = exception
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": CONF_LOCATION_ID}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: 9999}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_LOCATION_ID
    assert result["errors"] == {"base": error}


async def test_duplicate_location_subentry(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate OpenAQ location subentries abort."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": CONF_LOCATION_ID}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: LOCATION_ID}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_location_subentry_across_entries(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate OpenAQ location subentries across entries abort."""
    mock_config_entry.add_to_hass(hass)
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: "other-api-key"},
    )
    second_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (second_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": CONF_LOCATION_ID}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: LOCATION_ID}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
