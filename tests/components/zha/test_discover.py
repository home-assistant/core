"""Test zha device discovery."""

import re
from unittest import mock

import pytest

import homeassistant.components.zha.core.channels as zha_channels
import homeassistant.components.zha.core.channels.base as base_channels
import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.discovery as disc
import homeassistant.components.zha.core.gateway as core_zha_gw
import homeassistant.helpers.entity_registry

from .common import get_zha_gateway
from .zha_devices_list import DEVICES

NO_TAIL_ID = re.compile("_\\d$")


@pytest.mark.skip(reason="until refactoring is done")
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


@mock.patch(
    "homeassistant.components.zha.core.discovery.ProbeEndpoint.discover_by_device_type"
)
@mock.patch(
    "homeassistant.components.zha.core.discovery.ProbeEndpoint.discover_by_cluster_id"
)
def test_discover_entities(m1, m2):
    """Test discover endpoint class method."""
    ep_channels = mock.MagicMock()
    disc.probe.discover_entities(ep_channels)
    assert m1.call_count == 1
    assert m1.call_args[0][0] is ep_channels
    assert m2.call_count == 1
    assert m2.call_args[0][0] is ep_channels


@pytest.mark.parametrize(
    "device_type, component, hit",
    [
        (0x0100, zha_const.LIGHT, True),
        (0x0108, zha_const.SWITCH, True),
        (0x0051, zha_const.SWITCH, True),
        (0xFFFF, None, False),
    ],
)
def test_discover_by_device_type(device_type, component, hit):
    """Test entity discovery by device type."""

    ep_channels = mock.MagicMock(spec_set=zha_channels.EndpointChannels)
    ep_mock = mock.PropertyMock()
    ep_mock.return_value.profile_id = 0x0104
    ep_mock.return_value.device_type = device_type
    type(ep_channels).endpoint = ep_mock

    get_entity_mock = mock.MagicMock(
        return_value=(mock.sentinel.entity, mock.sentinel.claimed)
    )
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ):
        disc.probe.discover_by_device_type(ep_channels)
    if hit:
        assert get_entity_mock.call_count == 1
        assert ep_channels.claim_channels.call_count == 1
        assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
        assert ep_channels.async_new_entity.call_count == 1
        assert ep_channels.async_new_entity.call_args[0][0] == component
        assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity


def test_discover_by_device_type_override():
    """Test entity discovery by device type overriding."""

    ep_channels = mock.MagicMock(spec_set=zha_channels.EndpointChannels)
    ep_mock = mock.PropertyMock()
    ep_mock.return_value.profile_id = 0x0104
    ep_mock.return_value.device_type = 0x0100
    type(ep_channels).endpoint = ep_mock

    overrides = {ep_channels.unique_id: {"type": zha_const.SWITCH}}
    get_entity_mock = mock.MagicMock(
        return_value=(mock.sentinel.entity, mock.sentinel.claimed)
    )
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ):
        with mock.patch.dict(disc.probe._device_configs, overrides, clear=True):
            disc.probe.discover_by_device_type(ep_channels)
            assert get_entity_mock.call_count == 1
            assert ep_channels.claim_channels.call_count == 1
            assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
            assert ep_channels.async_new_entity.call_count == 1
            assert ep_channels.async_new_entity.call_args[0][0] == zha_const.SWITCH
            assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity


def test_discover_probe_single_cluster():
    """Test entity discovery by single cluster."""

    ep_channels = mock.MagicMock(spec_set=zha_channels.EndpointChannels)
    ep_mock = mock.PropertyMock()
    ep_mock.return_value.profile_id = 0x0104
    ep_mock.return_value.device_type = 0x0100
    type(ep_channels).endpoint = ep_mock

    get_entity_mock = mock.MagicMock(
        return_value=(mock.sentinel.entity, mock.sentinel.claimed)
    )
    channel_mock = mock.MagicMock(spec_set=base_channels.ZigbeeChannel)
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ):
        disc.probe.probe_single_cluster(zha_const.SWITCH, channel_mock, ep_channels)

    assert get_entity_mock.call_count == 1
    assert ep_channels.claim_channels.call_count == 1
    assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
    assert ep_channels.async_new_entity.call_count == 1
    assert ep_channels.async_new_entity.call_args[0][0] == zha_const.SWITCH
    assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity
    assert ep_channels.async_new_entity.call_args[0][3] == mock.sentinel.claimed
