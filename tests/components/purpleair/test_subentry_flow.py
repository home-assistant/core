"""PurpleAir subentry config flow tests."""

from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant.components.purpleair.const import (
    CONF_ADD_MAP_LOCATION,
    CONF_ADD_OPTIONS,
    CONF_ADD_SENSOR_INDEX,
    CONF_ALREADY_CONFIGURED,
    CONF_INVALID_API_KEY,
    CONF_NO_SENSOR_FOUND,
    CONF_NO_SENSORS_FOUND,
    CONF_SELECT_SENSOR,
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    CONF_UNKNOWN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_BASE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    CONF_DATA,
    CONF_ERRORS,
    CONF_FLOW_ID,
    CONF_NEXT_STEP_ID,
    CONF_SOURCE,
    CONF_STEP_ID,
    CONF_TYPE,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_RADIUS,
    TEST_SENSOR_INDEX1,
    TEST_SENSOR_READ_KEY,
)


async def test_create_from_map(
    hass: HomeAssistant, config_entry, setup_config_entry, mock_aiopurpleair, api
) -> None:
    """Test creating subentry from map."""

    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by map
    result = await hass.config_entries.subentries.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_MAP_LOCATION}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_MAP_LOCATION

    # Map location
    with patch.object(api, "sensors.async_get_nearby_sensors"):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_LOCATION: {
                    CONF_LATITUDE: TEST_LATITUDE,
                    CONF_LONGITUDE: TEST_LONGITUDE,
                    CONF_RADIUS: TEST_RADIUS,
                }
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_SELECT_SENSOR

    # Select and create
    with patch.object(api, "sensors.async_get_sensors"):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_SENSOR_INDEX: str(TEST_SENSOR_INDEX1),
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1}


async def test_create_from_index(
    hass: HomeAssistant, config_entry, setup_config_entry, mock_aiopurpleair, api
) -> None:
    """Test creating subentry from index and read key."""

    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by index
    result = await hass.config_entries.subentries.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR_INDEX}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR_INDEX

    # Enter index and create
    with patch.object(api, "sensors.async_get_sensors"):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1,
                CONF_SENSOR_READ_KEY: TEST_SENSOR_READ_KEY,
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1,
        CONF_SENSOR_READ_KEY: TEST_SENSOR_READ_KEY,
    }


async def test_duplicate_sensor(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test creating subentry from index and read key."""
    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by index
    result = await hass.config_entries.subentries.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR_INDEX}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR_INDEX

    # Enter index and create
    with patch.object(api, "sensors.async_get_sensors"):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1,
                CONF_SENSOR_READ_KEY: TEST_SENSOR_READ_KEY,
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_SENSOR_INDEX: CONF_ALREADY_CONFIGURED}


@pytest.mark.parametrize(
    ("get_nearby_sensors_mock", "get_nearby_sensors_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (AsyncMock(return_value=[]), {CONF_LOCATION: CONF_NO_SENSORS_FOUND}),
        (AsyncMock(return_value=None), {CONF_LOCATION: CONF_NO_SENSORS_FOUND}),
    ],
)
async def test_create_from_map_errors(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
    get_nearby_sensors_mock,
    get_nearby_sensors_errors,
) -> None:
    """Test creating subentry from map with errors."""

    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by map
    result = await hass.config_entries.subentries.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_MAP_LOCATION}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_MAP_LOCATION

    # Map location
    with patch.object(api.sensors, "async_get_nearby_sensors", get_nearby_sensors_mock):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_LOCATION: {
                    CONF_LATITUDE: TEST_LATITUDE,
                    CONF_LONGITUDE: TEST_LONGITUDE,
                    CONF_RADIUS: TEST_RADIUS,
                }
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == get_nearby_sensors_errors


@pytest.mark.parametrize(
    ("get_sensors_mock", "get_sensors_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (AsyncMock(return_value=[]), {CONF_SENSOR_INDEX: CONF_NO_SENSOR_FOUND}),
        (AsyncMock(return_value=None), {CONF_SENSOR_INDEX: CONF_NO_SENSOR_FOUND}),
    ],
)
async def test_create_from_index_errors(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
    get_sensors_mock,
    get_sensors_errors,
) -> None:
    """Test creating subentry from index and read key with errors."""

    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by index
    result = await hass.config_entries.subentries.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR_INDEX}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR_INDEX

    # Enter index and create
    with patch.object(api.sensors, "async_get_sensors", get_sensors_mock):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1,
                CONF_SENSOR_READ_KEY: TEST_SENSOR_READ_KEY,
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == get_sensors_errors

    hass.config_entries.subentries.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()
