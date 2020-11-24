"""Test the Google Maps Travel Time config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.google_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DESTINATION,
    CONF_LANGUAGE,
    CONF_MODE,
    CONF_OPTIONS,
    CONF_ORIGIN,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_UNIT_SYSTEM_IMPERIAL

from tests.async_mock import patch


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
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["step_id"] == "options"
        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == f"{DEFAULT_NAME}: location1 -> location2"
    assert result3["data"] == {
        CONF_API_KEY: "api_key",
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
        CONF_OPTIONS: {CONF_MODE: "driving"},
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_all_fields(hass):
    """Test user form with all fields."""
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
                CONF_NAME: "test_name",
            },
        )
        await hass.async_block_till_done()
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["step_id"] == "options"
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_MODE: "driving",
                CONF_LANGUAGE: "en",
                CONF_AVOID: "tolls",
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_ARRIVAL_TIME: "test",
                CONF_TRAFFIC_MODEL: "best_guess",
                CONF_TRANSIT_MODE: "train",
                CONF_TRANSIT_ROUTING_PREFERENCE: "less_walking",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "test_name"
    assert result3["data"] == {
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
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


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
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["step_id"] == "options"
        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})
        await hass.async_block_till_done()

        assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

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
        "homeassistant.components.google_travel_time.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
