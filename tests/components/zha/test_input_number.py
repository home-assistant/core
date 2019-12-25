"""Test zha analog output."""
from unittest.mock import MagicMock, call, patch

import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.input_number import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_init_zigpy_device,
    async_test_device_join,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

from tests.common import mock_coro


async def test_analog_output(hass, config_entry, zha_gateway):
    """Test zha analog output."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [general.AnalogOutput.cluster_id, general.Basic.cluster_id],
        [],
        None,
        zha_gateway,
    )

    async def get_chan_attr(*args, **kwargs):
        return {
            "present_value": 15.0,
            "max_present_value": 100.0,
            "min_present_value": 0.0,
            "relinquish_default": 50.0,
            "resolution": 1.0,
            "description": "PWM1",
            "engineering_units": 98,
            "application_type": 4 * 0x10000,
        }.get(args[0])

    with patch(
        "homeassistant.components.zha.core.channels.ZigbeeChannel.get_attribute_value",
        new=MagicMock(side_effect=get_chan_attr),
    ) as get_attr_mock:
        # load up input_number domain
        await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
        await hass.async_block_till_done()
        assert get_attr_mock.call_count == 8
        assert get_attr_mock.call_args[0][0] == "application_type"

    cluster = zigpy_device.endpoints.get(1).analog_output
    assert cluster is not None

    zha_device = zha_gateway.get_device(zigpy_device.ieee)
    assert zha_device is not None

    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the input_number was created and that its state is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    # test that the state has changed from unavailable to 15.0
    assert hass.states.get(entity_id).state == "15.0"

    # test attributes
    assert hass.states.get(entity_id).attributes.get("min") == 0.0
    assert hass.states.get(entity_id).attributes.get("max") == 100.0
    assert hass.states.get(entity_id).attributes.get("step") == 1.0
    assert hass.states.get(entity_id).attributes.get("mode") == "slider"
    assert hass.states.get(entity_id).attributes.get("initial") == 50.0
    assert hass.states.get(entity_id).attributes.get("icon") == "mdi:percent"
    assert hass.states.get(entity_id).attributes.get("unit_of_measurement") == "%"
    assert hass.states.get(entity_id).attributes.get("friendly_name") == "PWM1"

    # change value from device
    attr = make_attribute(0x0055, 15.0)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "15.0"

    # update value from device
    attr.value.value = 20.0
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "20.0"

    # change value from HA
    with patch(
        "zigpy.zcl.Cluster.write_attributes",
        return_value=mock_coro([zcl_f.Status.SUCCESS, zcl_f.Status.SUCCESS]),
    ):
        # set value via UI
        await hass.services.async_call(
            DOMAIN, "set_value", {"entity_id": entity_id, "value": 30.0}, blocking=True
        )
        assert len(cluster.write_attributes.mock_calls) == 1
        assert cluster.write_attributes.call_args == call({"present_value": 30.0})

    # test joining a new device to the network and HA
    await async_test_device_join(
        hass, zha_gateway, general.AnalogOutput.cluster_id, entity_id
    )
