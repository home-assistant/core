"""Define tests for the PurpleAir config flow."""

from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant.components.purpleair.const import (
    CONF_ALREADY_CONFIGURED,
    CONF_BASE,
    CONF_INVALID_API_KEY,
    CONF_MAP_LOCATION,
    CONF_NO_SENSORS_FOUND,
    CONF_REAUTH_CONFIRM,
    CONF_SELECT_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
    CONF_UNKNOWN,
    CONF_USER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    CONF_DATA,
    CONF_ERRORS,
    CONF_FLOW_ID,
    CONF_OPTIONS,
    CONF_REASON,
    CONF_REAUTH_SUCCESSFULL,
    CONF_SOURCE,
    CONF_STEP_ID,
    CONF_TYPE,
    TEST_API_KEY,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_NEW_API_KEY,
    TEST_RADIUS,
    TEST_SENSOR_INDEX1,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
@pytest.mark.parametrize(
    ("get_nearby_sensors_mock", "get_nearby_sensors_errors"),
    [
        (AsyncMock(return_value=[]), {CONF_BASE: CONF_NO_SENSORS_FOUND}),
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
async def test_create_entry_by_map_location(
    hass: HomeAssistant,
    api,
    check_api_key_errors,
    check_api_key_mock,
    get_nearby_sensors_errors,
    get_nearby_sensors_mock,
    mock_aiopurpleair,
) -> None:
    """Test creating an entry by from the map."""
    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_USER

    # API key
    with patch.object(api, "async_check_api_key", check_api_key_mock):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        assert result[CONF_TYPE] is FlowResultType.FORM
        assert result[CONF_ERRORS] == check_api_key_errors

    # Map location
    result = await hass.config_entries.flow.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_MAP_LOCATION

    # Nearby results
    with patch.object(api.sensors, "async_get_nearby_sensors", get_nearby_sensors_mock):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_LOCATION: {
                    CONF_LATITUDE: TEST_LATITUDE,
                    CONF_LONGITUDE: TEST_LONGITUDE,
                    CONF_RADIUS: TEST_RADIUS,
                }
            },
        )
        assert result[CONF_TYPE] is FlowResultType.FORM
        assert result[CONF_ERRORS] == get_nearby_sensors_errors

    # Select sensor
    result = await hass.config_entries.flow.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: TEST_LATITUDE,
                CONF_LONGITUDE: TEST_LONGITUDE,
                CONF_RADIUS: TEST_RADIUS,
            }
        },
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_SELECT_SENSOR

    # Create entry
    result = await hass.config_entries.flow.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_SENSOR_INDEX: [str(TEST_SENSOR_INDEX1)],
        },
    )
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_API_KEY: TEST_API_KEY,
    }
    assert result[CONF_OPTIONS] == {
        CONF_SENSOR_LIST: [
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None}
        ],
        CONF_SHOW_ON_MAP: False,
    }


async def test_duplicate_error(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test that the proper error is shown when adding a duplicate config entry."""
    # API key
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_API_KEY: TEST_API_KEY}
    )
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_ALREADY_CONFIGURED


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    mock_aiopurpleair,
    check_api_key_errors,
    check_api_key_mock,
    config_entry: MockConfigEntry,
    setup_config_entry,
) -> None:
    """Test re-auth (including errors)."""
    # Reauth
    result = await config_entry.start_reauth_flow(hass)
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_REAUTH_CONFIRM

    # API key
    with patch.object(mock_aiopurpleair, "async_check_api_key", check_api_key_mock):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        assert result[CONF_TYPE] is FlowResultType.FORM
        assert result[CONF_ERRORS] == check_api_key_errors

    # New entry
    result = await hass.config_entries.flow.async_configure(
        result[CONF_FLOW_ID],
        user_input={CONF_API_KEY: TEST_NEW_API_KEY},
    )
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_REAUTH_SUCCESSFULL
    assert len(hass.config_entries.async_entries()) == 1

    await hass.config_entries.async_unload(config_entry.entry_id)
