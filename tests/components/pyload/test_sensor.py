"""Tests for the pyLoad Sensors."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pyload.sensor import (
    SENSOR_TYPES,
    PyLoadSensor,
    async_setup_platform,
)
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component


async def test_setup(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of the pyload sensor platform."""

    assert await async_setup_component(hass, DOMAIN, pyload_config)
    await hass.async_block_till_done()

    result = hass.states.get("sensor.pyload_speed")
    assert result == snapshot


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (CannotConnect, PlatformNotReady),
        (ParserError, PlatformNotReady),
        (InvalidAuth, PlatformNotReady),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    expected_exception: Any,
) -> None:
    """Test exceptions during setup up pyLoad platform."""
    mock_async_add_entities = MagicMock()

    mock_pyloadapi.login.side_effect = exception

    with pytest.raises(expected_exception):
        await async_setup_platform(hass, pyload_config[DOMAIN], mock_async_add_entities)


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (CannotConnect, UpdateFailed),
        (ParserError, UpdateFailed),
        (InvalidAuth, UpdateFailed),
    ],
)
async def test_update_exceptions(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    expected_exception: Any,
) -> None:
    """Test exceptions during update of pyLoad sensor."""

    mock_pyloadapi.get_status.side_effect = exception

    new_sensor = PyLoadSensor(
        api=mock_pyloadapi,
        sensor_type=SENSOR_TYPES["speed"],
        client_name=pyload_config[DOMAIN][CONF_NAME],
    )

    with pytest.raises(expected_exception):
        await new_sensor.async_update()


async def test_update_invalidauth(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test non recoverable authentication error during update of pyLoad sensor."""

    mock_pyloadapi.get_status.side_effect = InvalidAuth
    mock_pyloadapi.login.side_effect = InvalidAuth

    new_sensor = PyLoadSensor(
        api=mock_pyloadapi,
        sensor_type=SENSOR_TYPES["speed"],
        client_name=pyload_config[DOMAIN][CONF_NAME],
    )

    with pytest.raises(PlatformNotReady):
        await new_sensor.async_update()
