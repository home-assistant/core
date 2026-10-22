"""Test the Google Maps Travel Time config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_travel_time.const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_REFERRER,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
    SECTION_API_KEY_OPTIONS,
    UNITS_IMPERIAL,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_MODE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ROUTES_RESPONSE, mock_compute_routes
from .const import DEFAULT_OPTIONS, MOCK_CONFIG, RECONFIGURE_CONFIG

REFERRER = "https://example.com/"

ERROR_RESPONSES = {
    "cannot_connect": {
        "status": 500,
        "json": {"error": {"message": "Internal error."}},
    },
    "timeout_connect": {"exc": TimeoutError()},
    "invalid_auth": {
        "status": 400,
        "json": {
            "error": {
                "message": "API key not valid.",
                "details": [{"reason": "API_KEY_INVALID"}],
            }
        },
    },
    "permission_denied": {
        "status": 403,
        "json": {
            "error": {
                "message": "Routes API has not been used in project.",
                "details": [{"reason": "SERVICE_DISABLED"}],
            }
        },
    },
    "invalid_referrer": {
        "status": 403,
        "json": {
            "error": {
                "message": "Requests from referer are blocked.",
                "details": [{"reason": "API_KEY_HTTP_REFERRER_BLOCKED"}],
            }
        },
    },
}


async def assert_common_reconfigure_steps(
    hass: HomeAssistant, reconfigure_result: ConfigFlowResult
) -> None:
    """Step through and assert the happy case reconfigure flow."""
    reconfigure_successful_result = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        RECONFIGURE_CONFIG,
    )
    assert reconfigure_successful_result["type"] is FlowResultType.ABORT
    assert reconfigure_successful_result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.title == DEFAULT_NAME
    assert entry.data == RECONFIGURE_CONFIG


async def assert_common_create_steps(
    hass: HomeAssistant, result: ConfigFlowResult
) -> None:
    """Step through and assert the happy case create flow."""
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "49.983862755708444,8.223882827079068",
    }


@pytest.mark.usefixtures("routes_mock", "mock_setup_entry")
async def test_minimum_fields(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    await assert_common_create_steps(hass, result)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_referrer(hass: HomeAssistant, routes_mock: AiohttpClientMocker) -> None:
    """Test creating an entry with a referrer."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **MOCK_CONFIG,
            SECTION_API_KEY_OPTIONS: {CONF_REFERRER: REFERRER},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**MOCK_CONFIG, CONF_REFERRER: REFERRER}
    assert routes_mock.mock_calls[0][3]["Referer"] == REFERRER


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [(kwargs, error) for error, kwargs in ERROR_RESPONSES.items()],
)
async def test_errors(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_kwargs: dict,
    error: str,
) -> None:
    """Test errors in the flow."""
    mock_compute_routes(routes_mock, **mock_kwargs)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_compute_routes(routes_mock, json=ROUTES_RESPONSE)
    await assert_common_create_steps(hass, result)


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("routes_mock", "mock_setup_entry")
async def test_reconfigure(hass: HomeAssistant, mock_config: MockConfigEntry) -> None:
    """Test reconfigure flow."""
    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    await assert_common_reconfigure_steps(hass, result)


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_referrer(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_config: MockConfigEntry,
) -> None:
    """Test reconfiguring an entry with a referrer."""
    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **RECONFIGURE_CONFIG,
            SECTION_API_KEY_OPTIONS: {CONF_REFERRER: REFERRER},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {**RECONFIGURE_CONFIG, CONF_REFERRER: REFERRER}
    assert routes_mock.mock_calls[-1][3]["Referer"] == REFERRER


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [(kwargs, error) for error, kwargs in ERROR_RESPONSES.items()],
)
async def test_reconfigure_invalid_config_entry(
    hass: HomeAssistant,
    mock_config: MockConfigEntry,
    routes_mock: AiohttpClientMocker,
    mock_kwargs: dict,
    error: str,
) -> None:
    """Test we get the form."""
    result = await mock_config.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    mock_compute_routes(routes_mock, **mock_kwargs)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        RECONFIGURE_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_compute_routes(routes_mock, json=ROUTES_RESPONSE)

    await assert_common_reconfigure_steps(hass, result)


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("routes_mock")
async def test_options_flow(hass: HomeAssistant, mock_config: MockConfigEntry) -> None:
    """Test options flow."""
    result = await hass.config_entries.options.async_init(mock_config.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "08:00",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_ARRIVAL_TIME: "08:00",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_ARRIVAL_TIME: "08:00",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("routes_mock")
async def test_options_flow_departure_time(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test options flow with departure time."""
    result = await hass.config_entries.options.async_init(mock_config.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: DEPARTURE_TIME,
            CONF_TIME: "08:00",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_DEPARTURE_TIME: "08:00",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_DEPARTURE_TIME: "08:00",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_DEPARTURE_TIME: "08:00",
            },
        ),
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_ARRIVAL_TIME: "08:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("routes_mock")
async def test_reset_departure_time(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test resetting departure time."""
    result = await hass.config_entries.options.async_init(mock_config.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: DEPARTURE_TIME,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_UNITS: UNITS_IMPERIAL,
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_ARRIVAL_TIME: "08:00",
            },
        ),
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_DEPARTURE_TIME: "08:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("routes_mock")
async def test_reset_arrival_time(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test resetting arrival time."""
    result = await hass.config_entries.options.async_init(mock_config.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_UNITS: UNITS_IMPERIAL,
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_TIME_TYPE: ARRIVAL_TIME,
                CONF_TIME: "08:00",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        )
    ],
)
@pytest.mark.usefixtures("routes_mock")
async def test_reset_options_flow_fields(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test resetting options flow fields that are not time related to None."""
    result = await hass.config_entries.options.async_init(mock_config.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "08:00",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_ARRIVAL_TIME: "08:00",
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("routes_mock", "mock_setup_entry")
async def test_dupe(hass: HomeAssistant, mock_config: MockConfigEntry) -> None:
    """Test setting up the same entry data twice is OK."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "49.983862755708444,8.223882827079068",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
