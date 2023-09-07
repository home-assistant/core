"""Test the Apple WeatherKit config flow."""
from unittest.mock import AsyncMock, patch

from apple_weatherkit.client import (
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientCommunicationError,
    WeatherKitApiClientError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.weatherkit.config_flow import (
    WeatherKitUnsupportedLocationError,
)
from homeassistant.components.weatherkit.const import (
    CONF_KEY_ID,
    CONF_KEY_PEM,
    CONF_SERVICE_ID,
    CONF_TEAM_ID,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

config_example_data = {
    CONF_NAME: "Home",
    CONF_LOCATION: {
        CONF_LATITUDE: 35.4690101707532,
        CONF_LONGITUDE: 135.74817234593166,
    },
    CONF_KEY_ID: "QABCDEFG123",
    CONF_SERVICE_ID: "io.home-assistant.testing",
    CONF_TEAM_ID: "ABCD123456",
    CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nwhateverkey\n-----END PRIVATE KEY-----",
}


async def _test_exception_generates_error(
    hass: HomeAssistant, exception: Exception, error: str
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "apple_weatherkit.client.WeatherKitApiClient.get_availability",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_example_data,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.weatherkit.config_flow.WeatherKitFlowHandler._test_config",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_example_data,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == config_example_data[CONF_NAME]
    assert result2["data"] == config_example_data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    await _test_exception_generates_error(
        hass, WeatherKitApiClientAuthenticationError, "auth"
    )


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection errors."""
    await _test_exception_generates_error(
        hass, WeatherKitApiClientCommunicationError, "connection"
    )


async def test_form_unsupported_location(hass: HomeAssistant) -> None:
    """Test we handle when WeatherKit does not support the location."""
    # Test throwing exception directly
    await _test_exception_generates_error(
        hass, WeatherKitUnsupportedLocationError, "unsupported_location"
    )

    # Test that no available data sets counts as unsupported as well
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "apple_weatherkit.client.WeatherKitApiClient.get_availability",
        return_value=[],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_example_data,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unsupported_location"}


async def test_form_unknown_client_error(hass: HomeAssistant) -> None:
    """Test we handle other client errors from the WeatherKit API."""
    await _test_exception_generates_error(hass, WeatherKitApiClientError, "unknown")
