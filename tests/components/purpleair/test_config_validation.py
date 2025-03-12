"""Define tests for the PurpleAir config flow."""

from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant.components.purpleair.config_validation import ConfigValidation
from homeassistant.components.purpleair.const import (
    CONF_INVALID_API_KEY,
    CONF_NO_SENSOR_FOUND,
    CONF_NO_SENSORS_FOUND,
    CONF_UNKNOWN,
)
from homeassistant.const import CONF_BASE
from homeassistant.core import HomeAssistant

from .const import (
    TEST_API_KEY,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_RADIUS,
    TEST_SENSOR_INDEX1,
)


@pytest.mark.parametrize(
    ("check_api_key_mock", "check_api_key_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (None, {}),
    ],
)
async def test_validate_api_key(
    hass: HomeAssistant,
    mock_aiopurpleair,
    api,
    check_api_key_mock,
    check_api_key_errors,
) -> None:
    """Test validate_api_key errors."""

    with (
        patch.object(api, "async_check_api_key", check_api_key_mock)
        if check_api_key_mock
        else patch.object(api, "async_check_api_key")
    ):
        result: ConfigValidation = await ConfigValidation.async_validate_api_key(
            hass, TEST_API_KEY
        )
        assert result.errors == check_api_key_errors


@pytest.mark.parametrize(
    ("get_nearby_sensors_mock", "get_nearby_sensors_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (AsyncMock(return_value=[]), {CONF_BASE: CONF_NO_SENSORS_FOUND}),
        (None, {}),
    ],
)
async def test_validate_coordinates(
    hass: HomeAssistant,
    mock_aiopurpleair,
    api,
    get_nearby_sensors_mock,
    get_nearby_sensors_errors,
) -> None:
    """Test validate_coordinates errors."""

    with (
        patch.object(api, "async_check_api_key"),
        patch.object(api, "sensor.async_get_nearby_sensors", get_nearby_sensors_mock)
        if get_nearby_sensors_mock
        else patch.object(api, "sensor.async_get_nearby_sensors"),
    ):
        result: ConfigValidation = await ConfigValidation.async_validate_coordinates(
            hass, TEST_API_KEY, TEST_LATITUDE, TEST_LONGITUDE, TEST_RADIUS
        )
        assert result.errors == get_nearby_sensors_errors
        if result.errors == {}:
            assert result.data is not None
        else:
            assert result.data is None


@pytest.mark.parametrize(
    ("get_sensors_mock", "get_sensors_errors"),
    [
        (AsyncMock(side_effect=Exception), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=PurpleAirError), {CONF_BASE: CONF_UNKNOWN}),
        (AsyncMock(side_effect=InvalidApiKeyError), {CONF_BASE: CONF_INVALID_API_KEY}),
        (AsyncMock(return_value=[]), {CONF_BASE: CONF_NO_SENSOR_FOUND}),
        (None, {}),
    ],
)
async def test_validate_sensor(
    hass: HomeAssistant,
    mock_aiopurpleair,
    api,
    get_sensors_mock,
    get_sensors_errors,
) -> None:
    """Test validate_sensor errors."""

    with (
        patch.object(api, "async_check_api_key"),
        patch.object(api, "sensors.async_get_sensors", get_sensors_mock)
        if get_sensors_mock
        else patch.object(api, "sensors.async_get_sensors"),
    ):
        result: ConfigValidation = await ConfigValidation.async_validate_sensor(
            hass, TEST_API_KEY, TEST_SENSOR_INDEX1, None
        )
        assert result.errors == get_sensors_errors
        if result.errors == {}:
            assert result.data is not None
        else:
            assert result.data is None
