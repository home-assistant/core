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
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import EXAMPLE_CONFIG_DATA

from tests.common import MockConfigEntry

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
    assert len(mock_setup_entry.mock_calls) == 1


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


async def test_reconfigure_of_disabled_v1_entry_migrates_old_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that reconfiguring a disabled, not-yet-migrated entry doesn't orphan its entities.

    A disabled config entry is never set up, so `async_migrate_entry` (which
    only runs as part of setup) never gets a chance to move its entities off
    their lat/lon-based unique ids before reconfigure changes the location.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data=EXAMPLE_CONFIG_DATA,
        version=1,
        disabled_by=config_entries.ConfigEntryDisabler.USER,
    )
    entry.add_to_hass(hass)

    old_unique_id = (
        f"{EXAMPLE_CONFIG_DATA[CONF_LATITUDE]}-{EXAMPLE_CONFIG_DATA[CONF_LONGITUDE]}"
    )

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, old_unique_id)},
    )
    weather_entity = entity_registry.async_get_or_create(
        Platform.WEATHER,
        DOMAIN,
        old_unique_id,
        config_entry=entry,
        device_id=device.id,
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    new_user_input = {
        CONF_LOCATION: {
            CONF_LATITUDE: 40.7127753,
            CONF_LONGITUDE: -74.0059728,
        },
        CONF_KEY_ID: EXAMPLE_CONFIG_DATA[CONF_KEY_ID],
        CONF_SERVICE_ID: EXAMPLE_CONFIG_DATA[CONF_SERVICE_ID],
        CONF_TEAM_ID: EXAMPLE_CONFIG_DATA[CONF_TEAM_ID],
        CONF_KEY_PEM: "",
    }

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Simulate the user later re-enabling the entry, which reloads (and thus
    # migrates) it the way it normally would be if it were never disabled.
    await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, entry.entry_id)}

    assert (
        entity_registry.async_get(weather_entity.entity_id).unique_id == entry.entry_id
    )


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test that reconfigure updates the entry's location and credentials."""
    entry = MockConfigEntry(domain=DOMAIN, title="Home", data=EXAMPLE_CONFIG_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_user_input = {
        CONF_LOCATION: {
            CONF_LATITUDE: 40.7127753,
            CONF_LONGITUDE: -74.0059728,
        },
        CONF_KEY_ID: "NEWKEY123456",
        CONF_SERVICE_ID: "io.home-assistant.testing",
        CONF_TEAM_ID: "ABCD123456",
        CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nanewkey\n-----END PRIVATE KEY-----",
    }

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    location = new_user_input[CONF_LOCATION]
    assert entry.data[CONF_LATITUDE] == location[CONF_LATITUDE]
    assert entry.data[CONF_LONGITUDE] == location[CONF_LONGITUDE]
    assert entry.data[CONF_KEY_ID] == new_user_input[CONF_KEY_ID]
    assert entry.data[CONF_KEY_PEM] == new_user_input[CONF_KEY_PEM]


async def test_reconfigure_flow_blank_key_pem_keeps_existing_key(
    hass: HomeAssistant,
) -> None:
    """Test that leaving the private key blank during reconfigure keeps the existing key."""
    entry = MockConfigEntry(domain=DOMAIN, title="Home", data=EXAMPLE_CONFIG_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    new_user_input = {
        CONF_LOCATION: {
            CONF_LATITUDE: 40.7127753,
            CONF_LONGITUDE: -74.0059728,
        },
        CONF_KEY_ID: EXAMPLE_CONFIG_DATA[CONF_KEY_ID],
        CONF_SERVICE_ID: EXAMPLE_CONFIG_DATA[CONF_SERVICE_ID],
        CONF_TEAM_ID: EXAMPLE_CONFIG_DATA[CONF_TEAM_ID],
        CONF_KEY_PEM: "",
    }

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    location = new_user_input[CONF_LOCATION]
    assert entry.data[CONF_LATITUDE] == location[CONF_LATITUDE]
    assert entry.data[CONF_LONGITUDE] == location[CONF_LONGITUDE]
    assert entry.data[CONF_KEY_PEM] == EXAMPLE_CONFIG_DATA[CONF_KEY_PEM]


async def test_reconfigure_flow_prefills_current_values(hass: HomeAssistant) -> None:
    """Test that the reconfigure form is prefilled with the entry's current values."""
    entry = MockConfigEntry(domain=DOMAIN, title="Home", data=EXAMPLE_CONFIG_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    schema = result["data_schema"].schema
    suggested_location = next(
        key.description["suggested_value"] for key in schema if key == CONF_LOCATION
    )
    assert suggested_location == {
        CONF_LATITUDE: EXAMPLE_CONFIG_DATA[CONF_LATITUDE],
        CONF_LONGITUDE: EXAMPLE_CONFIG_DATA[CONF_LONGITUDE],
    }

    suggested_key_id = next(
        key.description["suggested_value"] for key in schema if key == CONF_KEY_ID
    )
    assert suggested_key_id == EXAMPLE_CONFIG_DATA[CONF_KEY_ID]

    key_pem_key = next(key for key in schema if key == CONF_KEY_PEM)
    assert isinstance(key_pem_key, vol.Optional)
    assert key_pem_key.description is None


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (WeatherKitApiClientAuthenticationError, "invalid_auth"),
        (WeatherKitApiClientCommunicationError, "cannot_connect"),
        (WeatherKitUnsupportedLocationError, "unsupported_location"),
        (WeatherKitApiClientError, "unknown"),
    ],
)
async def test_reconfigure_flow_error_handling(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Test that reconfigure handles various exceptions and generates appropriate errors."""
    entry = MockConfigEntry(domain=DOMAIN, title="Home", data=EXAMPLE_CONFIG_DATA)
    entry.add_to_hass(hass)

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

    assert entry.data == EXAMPLE_CONFIG_DATA
