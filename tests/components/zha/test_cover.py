"""Test zha cover."""
import zigpy.zcl.clusters.closures as closures
import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.cover import DOMAIN
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_init_zigpy_device,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)


async def test_cover(hass, config_entry, zha_gateway):
    """Test zha cover platform."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [closures.WindowCovering.cluster_id, general.Basic.cluster_id],
        [],
        None,
        zha_gateway,
    )

    # load up cover domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).window_covering
    zha_device = zha_gateway.get_device(zigpy_device.ieee)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    attr = make_attribute(8, 100)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # test to see if it opens
    attr = make_attribute(8, 0)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OPEN
