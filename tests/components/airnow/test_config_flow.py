"""Test the AirNow config flow."""
from unittest.mock import patch

from pyairnow.errors import AirNowError, InvalidKeyError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.airnow.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS

from tests.common import MockConfigEntry

CONFIG = {
    CONF_API_KEY: "abc123",
    CONF_LATITUDE: 34.053718,
    CONF_LONGITUDE: -118.244842,
    CONF_RADIUS: 75,
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

    with patch("pyairnow.WebServiceAPI._get", return_value=MOCK_RESPONSE,), patch(
        "homeassistant.components.airnow.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.airnow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == CONFIG
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


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


async def test_entry_already_exists(hass):
    """Test that the form aborts if the Lat/Lng is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_id = f"{CONFIG[CONF_LATITUDE]}-{CONFIG[CONF_LONGITUDE]}"
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=mock_id)
    mock_entry.add_to_hass(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG,
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
