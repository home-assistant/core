"""Test zha device discovery."""

import asyncio
from unittest import mock

import pytest

import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.discovery as disc
import homeassistant.components.zha.core.gateway as core_zha_gw

from .zha_devices_list import DEVICES


@pytest.mark.parametrize("device", DEVICES)
async def test_devices(
    device, zha_gateway: core_zha_gw.ZHAGateway, hass, config_entry, zigpy_device_mock
):
    """Test device discovery."""

    zigpy_device = zigpy_device_mock(
        device["endpoints"],
        "00:11:22:33:44:55:66:77",
        device["manufacturer"],
        device["model"],
    )

    with mock.patch(
        "homeassistant.components.zha.core.discovery._async_create_cluster_channel",
        wraps=disc._async_create_cluster_channel,
    ):
        await zha_gateway.async_device_restored(zigpy_device)
        await hass.async_block_till_done()
        tasks = [
            hass.config_entries.async_forward_entry_setup(config_entry, component)
            for component in zha_const.COMPONENTS
        ]
        await asyncio.gather(*tasks)

        await hass.async_block_till_done()

        entity_ids = hass.states.async_entity_ids()
        await hass.async_block_till_done()
        zha_entities = {
            ent for ent in entity_ids if ent.split(".")[0] in zha_const.COMPONENTS
        }

        zha_dev = zha_gateway.get_device(zigpy_device.ieee)
        event_channels = {  # pylint: disable=protected-access
            ch.id for ch in zha_dev._relay_channels.values()
        }

        assert zha_entities == set(device["entities"])
        assert event_channels == set(device["event_channels"])
