"""Tests for gree component."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.components.gree.const import (
    COORDINATORS,
    DOMAIN as GREE,
    UPDATE_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import async_setup_gree, build_device_mock

from tests.common import async_fire_time_changed

ENTITY_ID_1 = f"{CLIMATE_DOMAIN}.fake_device_1"
ENTITY_ID_2 = f"{CLIMATE_DOMAIN}.fake_device_2"


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def test_discovery_after_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, discovery, device, mock_now
) -> None:
    """Test gree devices don't change after multiple discoveries."""
    mock_device_1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    mock_device_2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", mac="bbccdd223344"
    )

    discovery.return_value.mock_devices = [mock_device_1, mock_device_2]
    device.side_effect = [mock_device_1, mock_device_2]

    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 1
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2

    device_infos = [x.device.device_info for x in hass.data[GREE][COORDINATORS]]
    assert device_infos[0].ip == "1.1.1.1"
    assert device_infos[1].ip == "2.2.2.2"

    # rediscover the same devices with new ip addresses should update
    mock_device_1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.2", mac="aabbcc112233"
    )
    mock_device_2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.1", mac="bbccdd223344"
    )
    discovery.return_value.mock_devices = [mock_device_1, mock_device_2]
    device.side_effect = [mock_device_1, mock_device_2]

    next_update = mock_now + timedelta(minutes=6)
    freezer.move_to(next_update)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 2
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2

    device_infos = [x.device.device_info for x in hass.data[GREE][COORDINATORS]]
    assert device_infos[0].ip == "1.1.1.2"
    assert device_infos[1].ip == "2.2.2.1"


async def test_coordinator_updates(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, discovery, device
) -> None:
    """Test gree devices update their state."""
    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 1

    callback = device().add_handler.call_args_list[0][0][1]

    async def fake_update_state(*args) -> None:
        """Fake update state."""
        device().power = True
        callback()

    device().update_state.side_effect = fake_update_state

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state != HVACMode.OFF
