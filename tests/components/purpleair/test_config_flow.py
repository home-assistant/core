"""Define tests for the PurpleAir config flow."""

from typing import Any
from unittest.mock import AsyncMock

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant.components.purpleair.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_API_KEY, TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2

from tests.common import MockConfigEntry

TEST_LATITUDE = 51.5285582
TEST_LONGITUDE = -0.2416796


@pytest.mark.parametrize(
    ("check_api_key_side_effect", "check_api_key_errors"),
    [
        (Exception, "unknown"),
        (InvalidApiKeyError, "invalid_api_key"),
        (PurpleAirError, "unknown"),
    ],
)
@pytest.mark.parametrize(
    ("get_nearby_sensors_side_effect", "get_nearby_sensors_errors"),
    [
        ([[]], "no_sensors_near_coordinates"),
        (Exception, "unknown"),
        (PurpleAirError, "unknown"),
    ],
)
async def test_create_entry_by_coordinates(
    hass: HomeAssistant,
    check_api_key_errors: str,
    check_api_key_side_effect: type[Exception],
    get_nearby_sensors_errors: str,
    get_nearby_sensors_side_effect: list[Any] | type[Exception],
    mock_aiopurpleair: AsyncMock,
) -> None:
    """Test creating an entry by entering a latitude/longitude (including errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Test errors that can arise when checking the API key:
    mock_aiopurpleair.async_check_api_key.side_effect = check_api_key_side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": check_api_key_errors}

    mock_aiopurpleair.async_check_api_key.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "by_coordinates"

    # Test errors that can arise when searching for nearby sensors:
    mock_aiopurpleair.sensors.async_get_nearby_sensors.side_effect = (
        get_nearby_sensors_side_effect
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": get_nearby_sensors_errors}

    mock_aiopurpleair.sensors.async_get_nearby_sensors.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_sensor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "sensor_index": str(TEST_SENSOR_INDEX1),
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcde"
    assert result["data"] == {
        "api_key": TEST_API_KEY,
    }
    assert result["options"] == {
        "sensor_indices": [TEST_SENSOR_INDEX1],
    }


@pytest.mark.usefixtures("config_entry", "setup_config_entry")
async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that the proper error is shown when adding a duplicate config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": TEST_API_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        (Exception, "unknown"),
        (InvalidApiKeyError, "invalid_api_key"),
        (PurpleAirError, "unknown"),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_reauth(
    hass: HomeAssistant,
    mock_aiopurpleair: AsyncMock,
    error_msg: str,
    side_effect: type[Exception],
    config_entry: MockConfigEntry,
) -> None:
    """Test re-auth (including errors)."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Test errors that can arise when checking the API key:
    # with patch.object(mock_aiopurpleair, "async_check_api_key", check_api_key_mock):
    mock_aiopurpleair.async_check_api_key.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"api_key": "new_api_key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    mock_aiopurpleair.async_check_api_key.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"api_key": "new_api_key"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        ([[]], "no_sensors_near_coordinates"),
        (Exception, "unknown"),
        (PurpleAirError, "unknown"),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_options_add_sensor(
    hass: HomeAssistant,
    mock_aiopurpleair: AsyncMock,
    config_entry: MockConfigEntry,
    error_msg: str,
    side_effect: list[Any] | type[Exception],
) -> None:
    """Test adding a sensor via the options flow (including errors)."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_sensor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    # Test errors that can arise when searching for nearby sensors:

    mock_aiopurpleair.sensors.async_get_nearby_sensors.side_effect = side_effect

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_sensor"
    assert result["errors"] == {"base": error_msg}

    mock_aiopurpleair.sensors.async_get_nearby_sensors.side_effect = None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "sensor_index": str(TEST_SENSOR_INDEX2),
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
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


@pytest.mark.usefixtures("setup_config_entry")
async def test_options_add_sensor_duplicate(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test adding a duplicate sensor via the options flow."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_sensor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "latitude": TEST_LATITUDE,
            "longitude": TEST_LONGITUDE,
            "distance": 5,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "sensor_index": str(TEST_SENSOR_INDEX1),
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.usefixtures("setup_config_entry")
async def test_options_remove_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test removing a sensor via the options flow."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_sensor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "remove_sensor"

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(TEST_SENSOR_INDEX1)), config_entry.entry_id
    )
    assert device_entry is not None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"sensor_device_id": device_entry.id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor_indices": [],
    }

    assert config_entry.options["sensor_indices"] == []
    # Unload to make sure the update does not run after the
    # mock is removed.
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.usefixtures("setup_config_entry")
async def test_options_settings(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setting settings via the options flow."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "settings"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"show_on_map": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor_indices": [TEST_SENSOR_INDEX1],
        "show_on_map": True,
    }

    assert config_entry.options["show_on_map"] is True
