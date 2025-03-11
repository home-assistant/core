"""Define tests for the PurpleAir options flow."""

from unittest.mock import patch

from homeassistant.components.purpleair.const import (
    CONF_ADD_SENSOR,
    CONF_ALREADY_CONFIGURED,
    CONF_INIT,
    CONF_MAP_LOCATION,
    CONF_REMOVE_SENSOR,
    CONF_SELECT_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
    CONF_SETTINGS,
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


async def test_options_add_by_map(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
    mock_aiopurpleair,
) -> None:
    """Test adding sensors from the map."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select add by map
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_MAP_LOCATION}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_MAP_LOCATION

    # Map location
    with patch.object(mock_aiopurpleair.api.sensors, "async_get_nearby_sensors"):
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

    # Select and create
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
    await hass.async_block_till_done()
    assert config_entry.options[CONF_SENSOR_LIST] == [
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None},
    ]


async def test_options_add_map_duplicate(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test adding a duplicate sensor via the map selection."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select add by map
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

    # Select and create
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={
            CONF_SENSOR_INDEX: [str(TEST_SENSOR_INDEX1)],
        },
    )
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_ALREADY_CONFIGURED

    await hass.async_block_till_done()


async def test_options_add_by_index(
    hass: HomeAssistant, mock_aiopurpleair, config_entry, setup_config_entry
) -> None:
    """Test adding a sensor by index."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Add by index
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR

    # Enter index and create
    with patch.object(mock_aiopurpleair.api.sensors, "async_get_sensors"):
        result = await hass.config_entries.options.async_configure(
            result[CONF_FLOW_ID],
            user_input={CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2},
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
    await hass.async_block_till_done()
    assert config_entry.options[CONF_SENSOR_LIST] == [
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None},
        {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None},
    ]


async def test_options_add_index_duplicate(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
) -> None:
    """Test adding a duplicate sensor by index."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result[CONF_TYPE] is FlowResultType.MENU
    assert result[CONF_STEP_ID] == CONF_INIT

    # Select add by index
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR

    # Index and create
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID],
        user_input={CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1},
    )
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_ALREADY_CONFIGURED

    await hass.async_block_till_done()


async def test_options_remove_sensor(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
) -> None:
    """Test removing a sensor via the options flow."""

    # Options init
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
    await hass.async_block_till_done()
    assert config_entry.options[CONF_SENSOR_LIST] == []


async def test_options_settings(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test setting settings via the options flow."""

    # Options init
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
    await hass.async_block_till_done()
    assert config_entry.options[CONF_SHOW_ON_MAP] is True
