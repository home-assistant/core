"""Define tests for the PurpleAir config flow."""

from unittest.mock import patch

from homeassistant.components.purpleair.const import (
    CONF_ADD_OPTIONS,
    CONF_ADD_SENSOR,
    CONF_ALREADY_CONFIGURED,
    CONF_MAP_LOCATION,
    CONF_REAUTH_CONFIRM,
    CONF_REAUTH_SUCCESSFUL,
    CONF_SELECT_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
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
    CONF_FLOW_ID,
    CONF_NEXT_STEP_ID,
    CONF_OPTIONS,
    CONF_REASON,
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


async def test_create_entry_by_map(hass: HomeAssistant, mock_aiopurpleair) -> None:
    """Test creating an entry from the map."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_USER

    # API key
    with patch.object(mock_aiopurpleair.api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        assert result[CONF_TYPE] is FlowResultType.MENU
        assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by map
    result = await hass.config_entries.flow.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_MAP_LOCATION}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_MAP_LOCATION

    # Map location
    with patch.object(mock_aiopurpleair.api.sensors, "async_get_nearby_sensors"):
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

    # Select and create
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

    await hass.async_block_till_done()


async def test_create_entry_by_index(hass: HomeAssistant, mock_aiopurpleair) -> None:
    """Test creating an entry from index and read key."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_USER

    # API key
    with patch.object(mock_aiopurpleair.api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        assert result[CONF_TYPE] is FlowResultType.MENU
        assert result[CONF_STEP_ID] == CONF_ADD_OPTIONS

    # Add by index
    result = await hass.config_entries.flow.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_NEXT_STEP_ID: CONF_ADD_SENSOR}
    )
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_ADD_SENSOR

    # Enter index and create
    with patch.object(mock_aiopurpleair.api.sensors, "async_get_sensors"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID],
            user_input={CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1},
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

    await hass.async_block_till_done()


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

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries()) == 1


async def test_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiopurpleair,
) -> None:
    """Test reauth."""

    # Reauth
    result = await config_entry.start_reauth_flow(hass)
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_REAUTH_CONFIRM

    # API key
    with patch.object(mock_aiopurpleair.api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        assert result[CONF_TYPE] is FlowResultType.ABORT
        assert result[CONF_REASON] == CONF_REAUTH_SUCCESSFUL

    await hass.async_block_till_done()
    assert config_entry.data[CONF_API_KEY] == TEST_NEW_API_KEY
