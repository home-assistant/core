"""Test ZHA Gateway."""
import zigpy.zcl.clusters.general as general

import homeassistant.components.zha.core.const as zha_const

from .common import async_enable_traffic, async_init_zigpy_device


async def test_device_left(hass, config_entry, zha_gateway):
    """Test zha fan platform."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass, [general.Basic.cluster_id], [], None, zha_gateway
    )

    # load up fan domain
    await hass.config_entries.async_forward_entry_setup(config_entry, zha_const.SENSOR)
    await hass.async_block_till_done()

    zha_device = zha_gateway.get_device(zigpy_device.ieee)

    assert zha_device.available is False

    await async_enable_traffic(hass, zha_gateway, [zha_device])
    assert zha_device.available is True

    zha_gateway.device_left(zigpy_device)
    assert zha_device.available is False
