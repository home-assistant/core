"""Test the Google Maps Travel Time config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_travel_time.const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_LANGUAGE,
    CONF_OPTIONS,
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
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM_IMPERIAL,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


async def test_minimum_fields(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.google_travel_time.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "api_key",
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == f"{DEFAULT_NAME}: location1 -> location2"
    assert result2["data"] == {
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass):
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
        options={
            CONF_MODE: "driving",
            CONF_ARRIVAL_TIME: "test",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google_travel_time.sensor.GoogleTravelTimeSensor.update"
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TIME_TYPE: ARRIVAL_TIME,
            CONF_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert entry.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


async def test_options_flow_departure_time(hass):
    """Test options flow wiith departure time."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "api_key",
            CONF_ORIGIN: "location1",
            CONF_DESTINATION: "location2",
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google_travel_time.sensor.GoogleTravelTimeSensor.update"
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TIME_TYPE: DEPARTURE_TIME,
            CONF_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_DEPARTURE_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }

    assert entry.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_DEPARTURE_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }


async def test_dupe_id(hass):
    """Test setting up the same entry twice fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.google_travel_time.async_setup", return_value=True
    ), patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test",
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
            },
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
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

        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result2["reason"] == "already_configured"


async def test_import_flow(hass):
    """Test import_flow."""
    with patch(
        "homeassistant.components.google_travel_time.sensor.GoogleTravelTimeSensor.update"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_API_KEY: "api_key",
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
                CONF_NAME: "test_name",
                CONF_OPTIONS: {
                    CONF_MODE: "driving",
                    CONF_LANGUAGE: "en",
                    CONF_AVOID: "tolls",
                    CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                    CONF_ARRIVAL_TIME: "test",
                    CONF_TRAFFIC_MODEL: "best_guess",
                    CONF_TRANSIT_MODE: "train",
                    CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test_name"
    assert result["data"] == {
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
        CONF_NAME: "test_name",
        CONF_OPTIONS: {
            CONF_MODE: "driving",
            CONF_LANGUAGE: "en",
            CONF_AVOID: "tolls",
            CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_ARRIVAL_TIME: "test",
            CONF_TRAFFIC_MODEL: "best_guess",
            CONF_TRANSIT_MODE: "train",
            CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
        },
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
    }
    assert entry.options == {
        CONF_MODE: "driving",
        CONF_LANGUAGE: "en",
        CONF_AVOID: "tolls",
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ARRIVAL_TIME: "test",
        CONF_TRAFFIC_MODEL: "best_guess",
        CONF_TRANSIT_MODE: "train",
        CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
    }
