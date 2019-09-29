"""Test ZHA Device Tracker."""
from datetime import timedelta
import time
from homeassistant.components.device_tracker import DOMAIN, SOURCE_TYPE_ROUTER
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.components.zha.core.registries import (
    SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE,
)
import homeassistant.util.dt as dt_util
from .common import (
    async_init_zigpy_device,
    make_attribute,
    make_entity_id,
    async_test_device_join,
    async_enable_traffic,
)
from tests.common import async_fire_time_changed


async def test_device_tracker(hass, config_entry, zha_gateway):
    """Test zha device tracker platform."""
    from zigpy.zcl.clusters.general import (
        Basic,
        PowerConfiguration,
        BinaryInput,
        Identify,
        Ota,
        PollControl,
    )

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [
            Basic.cluster_id,
            PowerConfiguration.cluster_id,
            Identify.cluster_id,
            PollControl.cluster_id,
            BinaryInput.cluster_id,
        ],
        [Identify.cluster_id, Ota.cluster_id],
        SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE,
        zha_gateway,
    )

    # load up device tracker domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).power
    entity_id = make_entity_id(DOMAIN, zigpy_device, cluster, use_suffix=False)
    zha_device = zha_gateway.get_device(zigpy_device.ieee)

    # test that the device tracker was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    zigpy_device.last_seen = time.time() - 120
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    # test that the state has changed from unavailable to not home
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    # turn state flip
    attr = make_attribute(0x0020, 23)
    cluster.handle_message(False, 1, 0x0A, [[attr]])

    attr = make_attribute(0x0021, 200)
    cluster.handle_message(False, 1, 0x0A, [[attr]])

    zigpy_device.last_seen = time.time() + 10
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_HOME

    entity = hass.data[DOMAIN].get_entity(entity_id)

    assert entity.is_connected is True
    assert entity.source_type == SOURCE_TYPE_ROUTER
    assert entity.battery_level == 100

    # test adding device tracker to the network and HA
    await async_test_device_join(
        hass,
        zha_gateway,
        PowerConfiguration.cluster_id,
        DOMAIN,
        SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE,
    )
