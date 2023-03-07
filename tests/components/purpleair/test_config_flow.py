"""Define tests for the PurpleAir config flow."""
from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.purpleair import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_API_KEY, TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2

TEST_LATITUDE = 51.5285582
TEST_LONGITUDE = -0.2416796


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidApiKeyError), {"base": "invalid_api_key"}),
        (AsyncMock(side_effect=PurpleAirError), {"base": "unknown"}),
    ],
)
@pytest.mark.parametrize(
    ("get_nearby_sensors_mock", "get_nearby_sensors_errors"),
    [
        (AsyncMock(return_value=[]), {"base": "no_sensors_near_coordinates"}),
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=PurpleAirError), {"base": "unknown"}),
    ],
)
async def test_create_entry_by_coordinates(
    hass: HomeAssistant,
    api,
    check_api_key_errors,
    check_api_key_mock,
    get_nearby_sensors_errors,
    get_nearby_sensors_mock,
    mock_aiopurpleair,
) -> None:
    """Test creating an entry by entering a latitude/longitude (including errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise when checking the API key:
    with patch.object(api, "async_check_api_key", check_api_key_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"api_key": TEST_API_KEY}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == check_api_key_errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": TEST_API_KEY}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "by_coordinates"

    # Test errors that can arise when searching for nearby sensors:
    with patch.object(api.sensors, "async_get_nearby_sensors", get_nearby_sensors_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "latitude": TEST_LATITUDE,
                "longitude": TEST_LONGITUDE,
                "distance": 5,
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == get_nearby_sensors_errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "choose_sensor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "sensor_index": str(TEST_SENSOR_INDEX1),
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcde"
    assert result["data"] == {
        "api_key": TEST_API_KEY,
    }
    assert result["options"] == {
        "sensor_indices": [TEST_SENSOR_INDEX1],
    }


async def test_duplicate_error(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test that the proper error is shown when adding a duplicate config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"api_key": TEST_API_KEY}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidApiKeyError), {"base": "invalid_api_key"}),
        (AsyncMock(side_effect=PurpleAirError), {"base": "unknown"}),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    mock_aiopurpleair,
    check_api_key_errors,
    check_api_key_mock,
    config_entry,
    setup_config_entry,
) -> None:
    """Test re-auth (including errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
        },
        data={"api_key": TEST_API_KEY},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Test errors that can arise when checking the API key:
    with patch.object(mock_aiopurpleair, "async_check_api_key", check_api_key_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"api_key": "new_api_key"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == check_api_key_errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"api_key": "new_api_key"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("get_nearby_sensors_mock", "get_nearby_sensors_errors"),
    [
        (AsyncMock(return_value=[]), {"base": "no_sensors_near_coordinates"}),
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=PurpleAirError), {"base": "unknown"}),
    ],
)
async def test_options_add_sensor(
    hass: HomeAssistant,
    mock_aiopurpleair,
    config_entry,
    get_nearby_sensors_errors,
    get_nearby_sensors_mock,
    setup_config_entry,
) -> None:
    """Test adding a sensor via the options flow (including errors)."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_sensor"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    # Test errors that can arise when searching for nearby sensors:
    with patch.object(
        mock_aiopurpleair.sensors, "async_get_nearby_sensors", get_nearby_sensors_mock
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "latitude": TEST_LATITUDE,
                "longitude": TEST_LONGITUDE,
                "distance": 5,
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "add_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "choose_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "sensor_index": str(TEST_SENSOR_INDEX2),
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor_indices": [TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2],
    }

    assert config_entry.options["sensor_indices"] == [
        TEST_SENSOR_INDEX1,
        TEST_SENSOR_INDEX2,
    ]
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_add_sensor_duplicate(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test adding a duplicate sensor via the options flow."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_sensor"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "choose_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "sensor_index": str(TEST_SENSOR_INDEX1),
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_remove_sensor(
    hass: HomeAssistant, config_entry, setup_config_entry
) -> None:
    """Test removing a sensor via the options flow."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_sensor"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "remove_sensor"

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device({(DOMAIN, str(TEST_SENSOR_INDEX1))})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"sensor_device_id": device_entry.id},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor_indices": [],
    }

    assert config_entry.options["sensor_indices"] == []
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)
