"""Test the Waze Travel Time config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.waze_travel_time.const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_AVOID_FERRIES,
    DEFAULT_AVOID_SUBSCRIPTION_ROADS,
    DEFAULT_AVOID_TOLL_ROADS,
    DEFAULT_NAME,
    DEFAULT_REALTIME,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
)
from homeassistant.const import CONF_NAME, CONF_REGION, CONF_UNIT_SYSTEM_IMPERIAL

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
        "homeassistant.components.waze_travel_time.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.waze_travel_time.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
                CONF_REGION: "US",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
        CONF_REGION: "US",
        CONF_NAME: DEFAULT_NAME,
        CONF_REALTIME: DEFAULT_REALTIME,
        CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
        CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
        CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
        CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
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
        "homeassistant.components.waze_travel_time.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.waze_travel_time.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
                CONF_REGION: "US",
                CONF_NAME: "test_name",
                CONF_AVOID_FERRIES: True,
                CONF_AVOID_SUBSCRIPTION_ROADS: True,
                CONF_AVOID_TOLL_ROADS: True,
                CONF_EXCL_FILTER: "exclude",
                CONF_INCL_FILTER: "include",
                CONF_REALTIME: False,
                CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
                CONF_VEHICLE_TYPE: "taxi",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test_name"
    assert result2["data"] == {
        CONF_ORIGIN: "location1",
        CONF_DESTINATION: "location2",
        CONF_REGION: "US",
        CONF_NAME: "test_name",
        CONF_AVOID_FERRIES: True,
        CONF_AVOID_SUBSCRIPTION_ROADS: True,
        CONF_AVOID_TOLL_ROADS: True,
        CONF_EXCL_FILTER: "exclude",
        CONF_INCL_FILTER: "include",
        CONF_REALTIME: False,
        CONF_UNITS: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_VEHICLE_TYPE: "taxi",
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
        "homeassistant.components.waze_travel_time.async_setup", return_value=True
    ), patch(
        "homeassistant.components.waze_travel_time.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
                CONF_REGION: "US",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] is None

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: "location1",
                CONF_DESTINATION: "location2",
                CONF_REGION: "US",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result2["reason"] == "already_configured"
