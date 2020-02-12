"""Test zha device discovery."""

import re
from unittest import mock

import pytest

import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.discovery as disc
import homeassistant.components.zha.core.gateway as core_zha_gw
import homeassistant.helpers.entity_registry

from .common import get_zha_gateway
from .zha_devices_list import DEVICES

NO_TAIL_ID = re.compile("_\\d$")


@pytest.mark.parametrize("device", DEVICES)
async def test_devices(
    device, hass, zigpy_device_mock, monkeypatch, zha_device_joined_restored
):
    """Test device discovery."""

    zigpy_device = zigpy_device_mock(
        device["endpoints"],
        "00:11:22:33:44:55:66:77",
        device["manufacturer"],
        device["model"],
        node_descriptor=device["node_descriptor"],
    )

    _dispatch = mock.MagicMock(wraps=disc.async_dispatch_discovery_info)
    monkeypatch.setattr(core_zha_gw, "async_dispatch_discovery_info", _dispatch)
    entity_registry = await homeassistant.helpers.entity_registry.async_get_registry(
        hass
    )

    with mock.patch(
        "homeassistant.components.zha.core.discovery._async_create_cluster_channel",
        wraps=disc._async_create_cluster_channel,
    ):
        await zha_device_joined_restored(zigpy_device)
        await hass.async_block_till_done()

        entity_ids = hass.states.async_entity_ids()
        await hass.async_block_till_done()
        zha_entities = {
            ent for ent in entity_ids if ent.split(".")[0] in zha_const.COMPONENTS
        }

        zha_gateway = get_zha_gateway(hass)
        zha_dev = zha_gateway.get_device(zigpy_device.ieee)
        event_channels = {  # pylint: disable=protected-access
            ch.id for ch in zha_dev._relay_channels.values()
        }

        assert zha_entities == set(device["entities"])
        assert event_channels == set(device["event_channels"])

        entity_map = device["entity_map"]
        for calls in _dispatch.call_args_list:
            discovery_info = calls[0][2]
            unique_id = discovery_info["unique_id"]
            channels = discovery_info["channels"]
            component = discovery_info["component"]
            key = (component, unique_id)
            entity_id = entity_registry.async_get_entity_id(component, "zha", unique_id)

            assert key in entity_map
            assert entity_id is not None
            no_tail_id = NO_TAIL_ID.sub("", entity_map[key]["entity_id"])
            assert entity_id.startswith(no_tail_id)
            assert set([ch.name for ch in channels]) == set(entity_map[key]["channels"])
