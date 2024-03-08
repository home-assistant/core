"""Test the Google Maps Travel Time config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_travel_time.const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
    UNITS_IMPERIAL,
)
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG


@pytest.mark.usefixtures("validate_config_entry", "bypass_setup")
async def test_minimum_fields(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
    }


@pytest.mark.usefixtures("invalidate_config_entry")
async def test_invalid_config_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("invalid_api_key")
async def test_invalid_api_key(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.usefixtures("transport_error")
async def test_transport_error(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("timeout")
async def test_timeout(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "timeout_connect"}


async def test_malformed_api_key(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
            },
        )
    ],
)
@pytest.mark.usefixtures("validate_config_entry")
async def test_options_flow(hass: HomeAssistant, mock_config) -> None:
    """Test options flow."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
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
            },
        )
    ],
)
@pytest.mark.usefixtures("validate_config_entry")
async def test_options_flow_departure_time(hass: HomeAssistant, mock_config) -> None:
    """Test options flow with departure time."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: DEPARTURE_TIME,
            CONF_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_DEPARTURE_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_DEPARTURE_TIME: "test",
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
                CONF_DEPARTURE_TIME: "test",
            },
        ),
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
            },
        ),
    ],
)
@pytest.mark.usefixtures("validate_config_entry")
async def test_reset_departure_time(hass: HomeAssistant, mock_config) -> None:
    """Test resetting departure time."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: DEPARTURE_TIME,
        },
    )

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
                CONF_ARRIVAL_TIME: "test",
            },
        ),
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "driving",
                CONF_UNITS: UNITS_IMPERIAL,
                CONF_DEPARTURE_TIME: "test",
            },
        ),
    ],
)
@pytest.mark.usefixtures("validate_config_entry")
async def test_reset_arrival_time(hass: HomeAssistant, mock_config) -> None:
    """Test resetting arrival time."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
        },
    )

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
                CONF_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        )
    ],
)
@pytest.mark.usefixtures("validate_config_entry")
async def test_reset_options_flow_fields(hass: HomeAssistant, mock_config) -> None:
    """Test resetting options flow fields that are not time related to None."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_UNITS: UNITS_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "test",
        },
    )

    assert mock_config.options == {
        CONF_MODE: "driving",
        CONF_UNITS: UNITS_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
    }


@pytest.mark.usefixtures("validate_config_entry", "bypass_setup")
async def test_dupe(hass: HomeAssistant) -> None:
    """Test setting up the same entry data twice is OK."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
