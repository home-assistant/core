"""Test the Google Maps Travel Time config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
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
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG, RECONFIGURE_CONFIG

from tests.common import MockConfigEntry


async def assert_common_reconfigure_steps(
    hass: HomeAssistant, reconfigure_result: config_entries.ConfigFlowResult
) -> None:
    """Step through and assert the happy case reconfigure flow."""
    with (
        patch("homeassistant.components.google_travel_time.helpers.Client"),
        patch(
            "homeassistant.components.google_travel_time.helpers.distance_matrix",
            return_value=None,
        ),
    ):
        reconfigure_successful_result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            RECONFIGURE_CONFIG,
        )
        assert reconfigure_successful_result["type"] is FlowResultType.ABORT
        assert reconfigure_successful_result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data == RECONFIGURE_CONFIG


async def assert_common_create_steps(
    hass: HomeAssistant, user_step_result: config_entries.ConfigFlowResult
) -> None:
    """Step through and assert the happy case create flow."""
    with (
        patch("homeassistant.components.google_travel_time.helpers.Client"),
        patch(
            "homeassistant.components.google_travel_time.helpers.distance_matrix",
            return_value=None,
        ),
    ):
        create_result = await hass.config_entries.flow.async_configure(
            user_step_result["flow_id"],
            MOCK_CONFIG,
        )
        assert create_result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.title == DEFAULT_NAME
        assert entry.data == {
            CONF_NAME: DEFAULT_NAME,
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        }


@pytest.mark.usefixtures("validate_config_entry", "bypass_setup")
async def test_minimum_fields(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    await assert_common_create_steps(hass, result)


@pytest.mark.usefixtures("invalidate_config_entry")
async def test_invalid_config_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    await assert_common_create_steps(hass, result2)


@pytest.mark.usefixtures("invalid_api_key")
async def test_invalid_api_key(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    await assert_common_create_steps(hass, result2)


@pytest.mark.usefixtures("transport_error")
async def test_transport_error(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    await assert_common_create_steps(hass, result2)


@pytest.mark.usefixtures("timeout")
async def test_timeout(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "timeout_connect"}
    await assert_common_create_steps(hass, result2)


async def test_malformed_api_key(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
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
@pytest.mark.usefixtures("validate_config_entry", "bypass_setup")
async def test_reconfigure(hass: HomeAssistant, mock_config: MockConfigEntry) -> None:
    """Test reconfigure flow."""
    reconfigure_result = await mock_config.start_reconfigure_flow(hass)
    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"

    await assert_common_reconfigure_steps(hass, reconfigure_result)


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
@pytest.mark.usefixtures("invalidate_config_entry")
async def test_reconfigure_invalid_config_entry(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test we get the form."""
    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        RECONFIGURE_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    await assert_common_reconfigure_steps(hass, result2)


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
@pytest.mark.usefixtures("invalid_api_key")
async def test_reconfigure_invalid_api_key(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test we get the form."""
    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        RECONFIGURE_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    await assert_common_reconfigure_steps(hass, result2)


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
@pytest.mark.usefixtures("transport_error")
async def test_reconfigure_transport_error(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test we get the form."""
    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        RECONFIGURE_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    await assert_common_reconfigure_steps(hass, result2)


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
@pytest.mark.usefixtures("timeout")
async def test_reconfigure_timeout(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test we get the form."""
    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        RECONFIGURE_CONFIG,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "timeout_connect"}
    await assert_common_reconfigure_steps(hass, result2)


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
async def test_options_flow(hass: HomeAssistant, mock_config: MockConfigEntry) -> None:
    """Test options flow."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

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
            CONF_TIME: "test",
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
async def test_options_flow_departure_time(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test options flow with departure time."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

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
            CONF_TIME: "test",
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
async def test_reset_departure_time(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test resetting departure time."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

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
async def test_reset_arrival_time(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test resetting arrival time."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

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
async def test_reset_options_flow_fields(
    hass: HomeAssistant, mock_config: MockConfigEntry
) -> None:
    """Test resetting options flow fields that are not time related to None."""
    result = await hass.config_entries.options.async_init(
        mock_config.entry_id, data=None
    )

    assert result["type"] is FlowResultType.FORM
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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
