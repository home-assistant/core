"""Test ZHA Gateway."""
import pytest
import zigpy.zcl.clusters.general as general

from .common import async_enable_traffic, get_zha_gateway


@pytest.fixture
def zigpy_dev_basic(zigpy_device_mock):
    """Zigpy device with just a basic cluster."""
    return zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.Basic.cluster_id],
                "out_clusters": [],
                "device_type": 0,
            }
        },
    )


@pytest.fixture
async def zha_dev_basic(hass, zha_device_restored, zigpy_dev_basic):
    """ZHA device with just a basic cluster."""

    zha_device = await zha_device_restored(zigpy_dev_basic)
    return zha_device


async def test_device_left(hass, zigpy_dev_basic, zha_dev_basic):
    """Device leaving the network should become unavailable."""

    assert zha_dev_basic.available is False

    await async_enable_traffic(hass, [zha_dev_basic])
    assert zha_dev_basic.available is True

    get_zha_gateway(hass).device_left(zigpy_dev_basic)
    assert zha_dev_basic.available is False
