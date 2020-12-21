"""Test the AirNow config flow."""
from pyairnow.errors import AirNowError, InvalidKeyError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.airnow.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)

from tests.async_mock import patch

CONFIG = {
    CONF_API_KEY: "abc123",
    CONF_LATITUDE: 34.053718,
    CONF_LONGITUDE: -118.244842,
    CONF_RADIUS: 75,
    CONF_NAME: "Home",
}

# Mock AirNow Response
MOCK_RESPONSE = [
    {
        "DateObserved": "2020-12-20",
        "HourObserved": 15,
        "LocalTimeZone": "PST",
        "ReportingArea": "Central LA CO",
        "StateCode": "CA",
        "Latitude": 34.0663,
        "Longitude": -118.2266,
        "ParameterName": "O3",
        "AQI": 44,
        "Category": {
            "Number": 1,
            "Name": "Good",
        },
    },
    {
        "DateObserved": "2020-12-20",
        "HourObserved": 15,
        "LocalTimeZone": "PST",
        "ReportingArea": "Central LA CO",
        "StateCode": "CA",
        "Latitude": 34.0663,
        "Longitude": -118.2266,
        "ParameterName": "PM2.5",
        "AQI": 37,
        "Category": {
            "Number": 1,
            "Name": "Good",
        },
    },
    {
        "DateObserved": "2020-12-20",
        "HourObserved": 15,
        "LocalTimeZone": "PST",
        "ReportingArea": "Central LA CO",
        "StateCode": "CA",
        "Latitude": 34.0663,
        "Longitude": -118.2266,
        "ParameterName": "PM10",
        "AQI": 11,
        "Category": {
            "Number": 1,
            "Name": "Good",
        },
    },
]


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "pyairnow.WebServiceAPI._get",
        return_value=MOCK_RESPONSE,
    ) as mock_lat_long:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == CONFIG
    await hass.async_block_till_done()
    assert len(mock_lat_long.mock_calls) == 2


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyairnow.WebServiceAPI._get",
        side_effect=InvalidKeyError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_location(hass):
    """Test we handle invalid location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyairnow.WebServiceAPI._get", return_value={}):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_location"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyairnow.WebServiceAPI._get",
        side_effect=AirNowError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected(hass):
    """Test we handle an unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airnow.config_flow.validate_input",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
