"""Define tests for the PurpleAir options flow."""

from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import PurpleAirError
import pytest

from homeassistant.components.purpleair.const import (
    CONF_ADD_SENSOR,
    CONF_ALREADY_CONFIGURED,
    CONF_BASE,
    CONF_INIT,
    CONF_MAP_LOCATION,
    CONF_NO_SENSOR_FOUND,
    CONF_NO_SENSORS_FOUND,
    CONF_REMOVE_SENSOR,
    CONF_SELECT_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
    CONF_SETTINGS,
    CONF_UNKNOWN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DATA,
    CONF_FLOW_ID,
    CONF_NEXT_STEP_ID,
    CONF_REASON,
    CONF_STEP_ID,
    CONF_TYPE,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_RADIUS,
    TEST_SENSOR_INDEX1,
    TEST_SENSOR_INDEX2,
)


@pytest.mark.parametrize(
    ("get_nearby_sensors_mock", "get_nearby_sensors_errors"),
    [
        (AsyncMock(return_value=[]), {CONF_BASE: CONF_NO_SENSORS_FOUND}),
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
async def test_options_add_map_location(
    hass: HomeAssistant,
    mock_aiopurpleair,
    config_entry,
    get_nearby_sensors_errors,
    get_nearby_sensors_mock,
    setup_config_entry,
) -> None:
    """Test adding sensors from the map."""

    # Options menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select map
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_MAP_LOCATION}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_MAP_LOCATION

    # Map location
    with patch.object(
        mock_aiopurpleair.sensors, "async_get_nearby_sensors", get_nearby_sensors_mock
    ):
        result = await hass.config_entries.options.async_configure(
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
        assert result[CONF_STEP_ID] == CONF_MAP_LOCATION

    # Select
    result = await hass.config_entries.options.async_configure(
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

    # Create
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_SENSOR_INDEX: [str(TEST_SENSOR_INDEX2)],
        },
    )
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SENSOR_LIST: [
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None},
        ],
        CONF_SHOW_ON_MAP: False,
    }

    # New options
    assert config_entry.options[CONF_SENSOR_LIST] == [
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None},
    ]

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_add_map_duplicate(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test adding a duplicate sensor via the map selection."""

    # Options menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select map
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_MAP_LOCATION}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_MAP_LOCATION

    # Map location
    result = await hass.config_entries.options.async_configure(
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

    # Select
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_SENSOR_INDEX: [str(TEST_SENSOR_INDEX1)],
        },
    )
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_ALREADY_CONFIGURED

    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("get_sensors_mock", "get_sensors_errors"),
    [
        (AsyncMock(return_value=[]), {CONF_BASE: CONF_NO_SENSOR_FOUND}),
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
async def test_options_add_index(
    hass: HomeAssistant,
    mock_aiopurpleair,
    config_entry,
    get_sensors_errors,
    get_sensors_mock,
    setup_config_entry,
) -> None:
    """Test adding a sensor by index."""

    # Options menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select add by index
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR

    # Index
    with patch.object(mock_aiopurpleair.sensors, "async_get_sensors", get_sensors_mock):
        result = await hass.config_entries.options.async_configure(
            result[CONF_FLOW_ID],
            user_input={CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2},
        )
        assert result[CONF_TYPE] is FlowResultType.FORM
        assert result[CONF_STEP_ID] == CONF_ADD_SENSOR

    # Create
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2,
        },
    )
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SENSOR_LIST: [
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None},
        ],
        CONF_SHOW_ON_MAP: False,
    }

    # New options
    assert config_entry.options[CONF_SENSOR_LIST] == [
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None},
    ]

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_add_index_duplicate(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
) -> None:
    """Test adding a duplicate sensor by index."""

    # Options menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select add by index
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR

    # Index
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1},
    )
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_ALREADY_CONFIGURED

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_remove_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry,
    setup_config_entry,
) -> None:
    """Test removing a sensor via the options flow."""

    # Options menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select remove
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_REMOVE_SENSOR}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_REMOVE_SENSOR

    # Remove
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_SENSOR_INDEX: str(TEST_SENSOR_INDEX1),
        },
    )
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SENSOR_LIST: [],
        CONF_SHOW_ON_MAP: False,
    }

    # New options
    assert config_entry.options[CONF_SENSOR_LIST] == []

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_settings(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test setting settings via the options flow."""

    # Options menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select settings
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_SETTINGS}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_SETTINGS

    # Options
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_SHOW_ON_MAP: True}
    )
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SENSOR_LIST: [
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None}
        ],
        CONF_SHOW_ON_MAP: True,
    }

    # New options
    assert config_entry.options[CONF_SHOW_ON_MAP] is True
