"""Test the Apple WeatherKit config flow."""

from unittest.mock import AsyncMock, patch

from apple_weatherkit import DataSetType
from apple_weatherkit.client import (
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientCommunicationError,
    WeatherKitApiClientError,
)
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
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
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import EXAMPLE_CONFIG_DATA, init_integration

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

EXAMPLE_USER_INPUT = {
    CONF_LOCATION: {
        CONF_LATITUDE: 35.4690101707532,
        CONF_LONGITUDE: 135.74817234593166,
    },
    CONF_KEY_ID: "QABCDEFG123",
    CONF_SERVICE_ID: "io.home-assistant.testing",
    CONF_TEAM_ID: "ABCD123456",
    CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nwhateverkey\n-----END PRIVATE KEY-----",
}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    location = EXAMPLE_USER_INPUT[CONF_LOCATION]
    assert result["title"] == f"{location[CONF_LATITUDE]}, {location[CONF_LONGITUDE]}"

    assert result["data"] == EXAMPLE_CONFIG_DATA
    assert (
        result["result"].unique_id
        == f"{location[CONF_LATITUDE]}-{location[CONF_LONGITUDE]}"
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we abort if the location is already configured."""
    await init_integration(hass, unique_id="35.4690101707532-135.74817234593166")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (WeatherKitApiClientAuthenticationError, "invalid_auth"),
        (WeatherKitApiClientCommunicationError, "cannot_connect"),
        (WeatherKitUnsupportedLocationError, "unsupported_location"),
        (WeatherKitApiClientError, "unknown"),
    ],
)
async def test_error_handling(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Test that we handle various exceptions and generate appropriate errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_form_unsupported_location(hass: HomeAssistant) -> None:
    """Test we handle when WeatherKit does not support the location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_location"}

    # Test that we can recover from this error by changing the location
    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("input_header"),
    [
        "-----BEGIN PRIVATE KEY-----\n",
        "",
        "  \n\n-----BEGIN PRIVATE KEY-----\n",
        "—---BEGIN PRIVATE KEY-----\n",
    ],
    ids=["Correct header", "No header", "Leading characters", "Em dash in header"],
)
@pytest.mark.parametrize(
    ("input_footer"),
    [
        "\n-----END PRIVATE KEY-----",
        "",
        "\n-----END PRIVATE KEY-----\n\n  ",
        "\n—---END PRIVATE KEY-----",
    ],
    ids=["Correct footer", "No footer", "Trailing characters", "Em dash in footer"],
)
async def test_auto_fix_key_input(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    input_header: str,
    input_footer: str,
) -> None:
    """Test that we fix common user errors in key input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        user_input = EXAMPLE_USER_INPUT.copy()
        user_input[CONF_KEY_PEM] = f"{input_header}whateverkey{input_footer}"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["data"][CONF_KEY_PEM] == EXAMPLE_CONFIG_DATA[CONF_KEY_PEM]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfiguring an existing WeatherKit entry."""
    entry = await init_integration(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    new_user_input = {
        **EXAMPLE_USER_INPUT,
        CONF_LOCATION: {
            CONF_LATITUDE: 40.7128,
            CONF_LONGITUDE: -74.006,
        },
        CONF_KEY_ID: "new-key-id",
        CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nnewkey\n-----END PRIVATE KEY-----",
    }

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_LATITUDE] == 40.7128
    assert entry.data[CONF_LONGITUDE] == -74.006
    assert entry.data[CONF_KEY_ID] == "new-key-id"
    assert entry.data[CONF_KEY_PEM] == new_user_input[CONF_KEY_PEM]
    assert entry.unique_id == "40.7128--74.006"


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfiguring to a location used by another entry aborts."""
    other_location = {
        CONF_LATITUDE: 40.7128,
        CONF_LONGITUDE: -74.006,
    }
    await init_integration(
        hass,
        unique_id=f"{other_location[CONF_LATITUDE]}-{other_location[CONF_LONGITUDE]}",
    )
    entry = await init_integration(
        hass, unique_id="35.4690101707532-135.74817234593166"
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**EXAMPLE_USER_INPUT, CONF_LOCATION: other_location},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_migrates_entity_and_device_unique_ids(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that changing location during reconfigure migrates existing unique IDs."""
    old_unique_id = "35.4690101707532-135.74817234593166"
    entry = await init_integration(hass, unique_id=old_unique_id)

    weather_entity = entity_registry.async_get_or_create(
        WEATHER_DOMAIN, DOMAIN, old_unique_id, config_entry=entry
    )
    sensor_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{old_unique_id}_pressureTrend",
        config_entry=entry,
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, old_unique_id)},
        manufacturer="Apple Weather",
        name=entry.title,
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    new_user_input = {
        **EXAMPLE_USER_INPUT,
        CONF_LOCATION: {
            CONF_LATITUDE: 40.7128,
            CONF_LONGITUDE: -74.006,
        },
    }

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    new_unique_id = "40.7128--74.006"
    assert entry.unique_id == new_unique_id
    assert (
        entity_registry.async_get(weather_entity.entity_id).unique_id == new_unique_id
    )
    assert (
        entity_registry.async_get(sensor_entity.entity_id).unique_id
        == f"{new_unique_id}_pressureTrend"
    )
    assert device_registry.async_get(device.id).identifiers == {(DOMAIN, new_unique_id)}


async def test_reconfigure_flow_blank_key_pem_keeps_current_value(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that leaving the private key blank during reconfigure keeps the current value."""
    entry = await init_integration(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    schema = result["data_schema"]
    suggested_values = {
        key.schema: key.description.get("suggested_value")
        for key in schema.schema
        if isinstance(key, vol.Marker)
        and key.description
        and "suggested_value" in key.description
    }
    assert suggested_values[CONF_KEY_PEM] == ""

    new_user_input = {
        **EXAMPLE_USER_INPUT,
        CONF_KEY_ID: "new-key-id",
        CONF_KEY_PEM: "",
    }

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_KEY_ID] == "new-key-id"
    assert entry.data[CONF_KEY_PEM] == EXAMPLE_CONFIG_DATA[CONF_KEY_PEM]


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (WeatherKitApiClientAuthenticationError, "invalid_auth"),
        (WeatherKitApiClientCommunicationError, "cannot_connect"),
        (WeatherKitUnsupportedLocationError, "unsupported_location"),
        (WeatherKitApiClientError, "unknown"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test that the reconfigure flow handles errors and can recover."""
    entry = await init_integration(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
