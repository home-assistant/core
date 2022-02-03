"""Tests for gree component."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.climate.const import DOMAIN
from homeassistant.components.gree.const import COORDINATORS, DOMAIN as GREE
import homeassistant.util.dt as dt_util

from .common import async_setup_gree, build_device_mock

from tests.common import async_fire_time_changed

ENTITY_ID_1 = f"{DOMAIN}.fake_device_1"
ENTITY_ID_2 = f"{DOMAIN}.fake_device_2"


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def test_discovery_after_setup(hass, discovery, device, mock_now):
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
    assert len(hass.states.async_all(DOMAIN)) == 2

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
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 2
    assert len(hass.states.async_all(DOMAIN)) == 2

    device_infos = [x.device.device_info for x in hass.data[GREE][COORDINATORS]]
    assert device_infos[0].ip == "1.1.1.2"
    assert device_infos[1].ip == "2.2.2.1"
