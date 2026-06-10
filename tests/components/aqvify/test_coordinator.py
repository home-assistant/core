"""Test Aqvify coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
from pyaqvify import AqvifyAuthException
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

WATER_LEVEL_SENSOR = "sensor.device_1_water_level"
EXPECTED_WATER_LEVEL = "-0.136786005"


@pytest.mark.parametrize(
    ("exception", "last_exception", "expected_state"),
    [
        (TimeoutError, UpdateFailed, EXPECTED_WATER_LEVEL),
        (
            ClientResponseError(Mock(), Mock(), status=500),
            UpdateFailed,
            EXPECTED_WATER_LEVEL,
        ),
        (AqvifyAuthException, ConfigEntryAuthFailed, "unavailable"),
    ],
    ids=["timeout_error", "communications_error", "auth_error"],
)
async def test_coordinator_get_devices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    last_exception: Exception,
    expected_state: str,
) -> None:
    """Tests that the coordinator handles errors from async_get_devices."""

    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    mock_aqvify_client.async_get_devices.side_effect = exception

    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == STATE_UNAVAILABLE
    assert isinstance(coordinator.last_exception, last_exception)

    mock_aqvify_client.async_get_devices.side_effect = None
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == expected_state


@pytest.mark.parametrize(
    ("exception", "last_exception", "expected_state"),
    [
        (TimeoutError, UpdateFailed, EXPECTED_WATER_LEVEL),
        (
            ClientResponseError(Mock(), Mock(), status=500),
            UpdateFailed,
            EXPECTED_WATER_LEVEL,
        ),
        (AqvifyAuthException, ConfigEntryAuthFailed, "unavailable"),
    ],
)
async def test_coordinator_get_device_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    last_exception: Exception,
    expected_state: str,
) -> None:
    """Tests that the coordinator handles errors from async_get_device_latest_data."""

    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    mock_aqvify_client.async_get_device_latest_data.side_effect = exception

    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == STATE_UNAVAILABLE
    assert isinstance(coordinator.last_exception, last_exception)

    mock_aqvify_client.async_get_device_latest_data.side_effect = None
    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WATER_LEVEL_SENSOR).state == expected_state
