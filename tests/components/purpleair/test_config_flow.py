"""Define tests for the PurpleAir config flow."""

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
    CONF_REAUTH_CONFIRM,
    CONF_REAUTH_SUCCESSFUL,
    CONF_RECONFIGURE,
    CONF_RECONFIGURE_SUCCESSFUL,
    CONF_SELECT_SENSOR,
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    CONF_SETTINGS,
    CONF_UNKNOWN,
    DOMAIN,
    TITLE,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BASE,
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
    CONF_NEXT_STEP_ID,
    CONF_OPTIONS,
    CONF_REASON,
    CONF_SOURCE,
    CONF_SOURCE_USER,
    CONF_STEP_ID,
    CONF_TITLE,
    CONF_TYPE,
    TEST_API_KEY,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_NEW_API_KEY,
    TEST_RADIUS,
    TEST_SENSOR_INDEX1,
    TEST_SENSOR_READ_KEY,
)


async def test_user_init(hass: HomeAssistant, mock_aiopurpleair, api) -> None:
    """Test user initialization flow."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_API_KEY: TEST_API_KEY,
    }
    assert result[CONF_OPTIONS] == {
        CONF_SHOW_ON_MAP: False,
    }
    assert result[CONF_TITLE] == TITLE

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Add second entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # Different API key for second entry
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_API_KEY: TEST_NEW_API_KEY,
    }
    assert result[CONF_TITLE] == f"{TITLE} (1)"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


async def test_reconfigure(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test reconfigure."""

    # Reconfigure
    result = await config_entry.start_reconfigure_flow(hass)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_RECONFIGURE

    # Bad API key
    with patch.object(
        api, "async_check_api_key", AsyncMock(side_effect=InvalidApiKeyError)
    ):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_API_KEY: CONF_INVALID_API_KEY}

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_RECONFIGURE_SUCCESSFUL

    assert config_entry.data[CONF_API_KEY] == TEST_NEW_API_KEY


async def test_reauth(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test reauth."""

    # Reauth
    result = await config_entry.start_reauth_flow(hass)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_REAUTH_CONFIRM

    # Bad API key
    with patch.object(
        api, "async_check_api_key", AsyncMock(side_effect=InvalidApiKeyError)
    ):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_API_KEY: CONF_INVALID_API_KEY}

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_NEW_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == CONF_REAUTH_SUCCESSFUL

    assert config_entry.data[CONF_API_KEY] == TEST_NEW_API_KEY


async def test_duplicate_api_key(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
) -> None:
    """Test duplicate API key flow."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # API key
    with patch.object(api, "async_check_api_key"):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == {CONF_API_KEY: CONF_ALREADY_CONFIGURED}

    hass.config_entries.flow.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (
            AsyncMock(side_effect=InvalidApiKeyError),
            {CONF_API_KEY: CONF_INVALID_API_KEY},
        ),
        (AsyncMock(return_value=None), {CONF_BASE: CONF_UNKNOWN}),
    ],
)
async def test_user_init_errors(
    hass: HomeAssistant,
    mock_aiopurpleair,
    api,
    check_api_key_mock,
    check_api_key_errors,
) -> None:
    """Test user initialization flow."""

    # User init
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: CONF_SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_API_KEY

    # API key
    with patch.object(api, "async_check_api_key", check_api_key_mock):
        result = await hass.config_entries.flow.async_configure(
            result[CONF_FLOW_ID], user_input={CONF_API_KEY: TEST_API_KEY}
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == check_api_key_errors

    hass.config_entries.flow.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


async def test_options_settings(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test options setting flow."""

    # Options init
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == CONF_SETTINGS

    # Settings
    result = await hass.config_entries.options.async_configure(
        result[CONF_FLOW_ID], user_input={CONF_SHOW_ON_MAP: True}
    )
    await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_DATA] == {
        CONF_SHOW_ON_MAP: True,
    }


async def test_create_from_map(
    hass: HomeAssistant, config_entry, setup_config_entry, mock_aiopurpleair, api
) -> None:
    """Test creating subentry from map."""

    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: CONF_SOURCE_USER}
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
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: CONF_SOURCE_USER}
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
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: CONF_SOURCE_USER}
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

    hass.config_entries.subentries.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


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
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: CONF_SOURCE_USER}
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

    hass.config_entries.subentries.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


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
async def test_create_from_map_select_errors(
    hass: HomeAssistant,
    config_entry,
    setup_config_entry,
    mock_aiopurpleair,
    api,
    get_sensors_mock,
    get_sensors_errors,
) -> None:
    """Test creating subentry from map with select errors."""

    # User init
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: CONF_SOURCE_USER}
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
    with patch.object(api.sensors, "async_get_sensors", get_sensors_mock):
        result = await hass.config_entries.subentries.async_configure(
            result[CONF_FLOW_ID],
            user_input={
                CONF_SENSOR_INDEX: str(TEST_SENSOR_INDEX1),
            },
        )
        await hass.async_block_till_done()
    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_ERRORS] == get_sensors_errors

    hass.config_entries.subentries.async_abort(result[CONF_FLOW_ID])
    await hass.async_block_till_done()


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
        (config_entry.entry_id, CONF_SENSOR), context={CONF_SOURCE: CONF_SOURCE_USER}
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
