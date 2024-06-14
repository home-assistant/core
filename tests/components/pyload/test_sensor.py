"""Tests for the pyLoad Sensors."""

from unittest.mock import AsyncMock

from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("mock_pyloadapi")
async def test_setup(
    hass: HomeAssistant,
    pyload_config: ConfigType,
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
        (CannotConnect, "Unable to connect and retrieve data from pyLoad API"),
        (ParserError, "Unable to parse data from pyLoad API"),
        (
            InvalidAuth,
            "Authentication failed for username, check your login credentials",
        ),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    expected_exception: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exceptions during setup up pyLoad platform."""

    mock_pyloadapi.login.side_effect = exception

    assert await async_setup_component(hass, DOMAIN, pyload_config)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(DOMAIN)) == 0
    assert expected_exception in caplog.text


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (CannotConnect, "UpdateFailed"),
        (ParserError, "UpdateFailed"),
        (InvalidAuth, "UpdateFailed"),
    ],
)
async def test_sensor_update_exceptions(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    expected_exception: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exceptions during update of pyLoad sensor."""

    mock_pyloadapi.get_status.side_effect = exception

    assert await async_setup_component(hass, DOMAIN, pyload_config)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(DOMAIN)) == 0
    assert expected_exception in caplog.text
