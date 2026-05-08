"""Test the OpenAQ config flow."""

from collections.abc import Sequence
from typing import cast
from unittest.mock import AsyncMock, call

import httpx
from openaq import (
    ApiKeyMissingError,
    ForbiddenError,
    HTTPRateLimitError,
    NotAuthorizedError,
    RateLimitError,
)
from openaq.shared.exceptions import APIError
import pytest

from homeassistant import config_entries
from homeassistant.components.openaq.config_flow import OpenAQLocationFlowData
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
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector

from .conftest import API_KEY, LOCATION_ID, make_location, make_response

from tests.common import MockConfigEntry


def _get_select_options(result: FlowResult) -> Sequence[SelectOptionDict]:
    """Return select options from a flow result."""
    data_schema = result["data_schema"]
    assert data_schema is not None
    selector = next(iter(data_schema.schema.values()))
    assert isinstance(selector, SelectSelector)
    return cast(Sequence[SelectOptionDict], selector.config["options"])


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
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NotAuthorizedError("Invalid API key"), "invalid_auth"),
        (HTTPRateLimitError("Rate limited"), "rate_limited"),
        (APIError("API error"), "cannot_connect"),
        (httpx.ConnectError("Connection error"), "cannot_connect"),
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
    """Test duplicate parent setup aborts for the same API key."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_openaq_client.parameters.list.assert_not_awaited()


async def test_different_api_key_parent_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a parent entry can be added for a different API key."""
    mock_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_API_KEY: "other-api-key"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "other-api-key"}


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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
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


async def test_location_subentry_map_flow_without_locality(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an OpenAQ location without a separate locality."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response(
        [make_location(location_id=9999, name="Albuquerque")]
    )
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: "9999"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Albuquerque"


async def test_location_subentry_map_flow_sorts_by_sensor_count_before_distance(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search ranks useful locations by sensor count before distance."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.side_effect = [
        make_response(
            [
                make_location(
                    location_id=9998,
                    name="Nearby",
                    locality="Nearby",
                    distance=1000,
                    sensor_parameters=("o3",),
                )
            ]
        ),
        make_response(
            [
                make_location(
                    location_id=9999,
                    name="Pinecliff",
                    locality="Pinecliff",
                    distance=6000,
                    sensor_parameters=("pm1", "pm10", "pm25"),
                )
            ]
        ),
    ]
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 10000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    assert _get_select_options(result) == [
        SelectOptionDict(
            value="9999",
            label="Pinecliff - 3 sensors: PM1, PM10, PM2.5 - 6.0 km",
        ),
        SelectOptionDict(value="9998", label="Nearby - 1 sensor: Ozone - 1.0 km"),
    ]
    assert mock_openaq_client.locations.list.await_args_list == [
        call(coordinates=(35.1, -106.6), radius=5000, limit=10),
        call(coordinates=(35.1, -106.6), radius=10000, limit=10),
    ]


async def test_location_subentry_map_flow_labels_unknown_distance(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search labels locations with unknown distances."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response(
        [make_location(location_id=9999, distance=None)]
    )
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert _get_select_options(result) == [
        SelectOptionDict(
            value="9999",
            label="Del Norte, Albuquerque - 1 sensor: PM2.5 - unknown distance",
        )
    ]


async def test_location_subentry_map_flow_limits_to_top_five_locations(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search only shows the top five useful locations."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response(
        [
            make_location(location_id=9991, name="Location 1", distance=100),
            make_location(location_id=9992, name="Location 2", distance=200),
            make_location(location_id=9993, name="Location 3", distance=300),
            make_location(location_id=9994, name="Location 4", distance=400),
            make_location(location_id=9995, name="Location 5", distance=500),
            make_location(location_id=9996, name="Location 6", distance=600),
        ]
    )
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert [option["value"] for option in _get_select_options(result)] == [
        "9991",
        "9992",
        "9993",
        "9994",
        "9995",
    ]


async def test_location_subentry_map_flow_omits_locations_without_supported_sensors(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search omits locations with only unsupported sensors."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response(
        [
            make_location(
                location_id=9998,
                name="Unsupported",
                sensor_parameters=("temperature",),
            ),
            make_location(location_id=9999, name="Supported"),
        ]
    )
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert [option["value"] for option in _get_select_options(result)] == ["9999"]


async def test_location_subentry_map_flow_deduplicates_locations_across_radius_searches(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search deduplicates location IDs across radius searches."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.side_effect = [
        make_response([make_location(location_id=9998, name="Duplicate")]),
        make_response(
            [
                make_location(location_id=9998, name="Duplicate"),
                make_location(location_id=9999, name="Other"),
            ]
        ),
    ]
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 10000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert [option["value"] for option in _get_select_options(result)] == [
        "9998",
        "9999",
    ]


async def test_location_subentry_map_flow_expands_radius_for_useful_locations(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test map search expands the radius when nearby results are not useful."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.side_effect = [
        make_response(
            [
                make_location(
                    location_id=9998,
                    name="Unsupported",
                    sensor_parameters=("temperature",),
                )
            ]
        ),
        make_response([make_location(location_id=9999, name="Supported")]),
    ]
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 10000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert [option["value"] for option in _get_select_options(result)] == ["9999"]
    assert mock_openaq_client.locations.list.await_args_list == [
        call(coordinates=(35.1, -106.6), radius=5000, limit=10),
        call(coordinates=(35.1, -106.6), radius=10000, limit=10),
    ]


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
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_locations_found"}


def test_location_select_label_without_supported_parameters() -> None:
    """Test location select label with no supported parameters."""
    location = OpenAQLocationFlowData(location_id=9999, title="Del Norte")

    assert location.select_label == "Del Norte"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ApiKeyMissingError("Missing API key"), "invalid_auth"),
        (ForbiddenError("Forbidden"), "invalid_auth"),
        (NotAuthorizedError("Invalid API key"), "invalid_auth"),
        (HTTPRateLimitError("Rate limited"), "rate_limited"),
        (RateLimitError("Rate limited"), "rate_limited"),
        (APIError("API error"), "cannot_connect"),
        (httpx.ConnectError("Connection error"), "cannot_connect"),
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
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}


async def test_duplicate_location_subentry_from_map_selection(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate OpenAQ location selected from map aborts."""
    mock_config_entry.add_to_hass(hass)
    mock_openaq_client.locations.list.return_value = make_response([make_location()])
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: str(LOCATION_ID)}
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
        result["flow_id"],
        {
            ATTR_LOCATION: {
                ATTR_LATITUDE: 35.1,
                ATTR_LONGITUDE: -106.6,
                CONF_RADIUS: 5000,
            },
            CONF_LIMIT: 10,
        },
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: str(LOCATION_ID)}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
