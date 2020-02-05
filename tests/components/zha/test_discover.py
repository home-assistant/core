"""Test zha device discovery."""

import re
from unittest import mock

import pytest

import homeassistant.components.zha.core.channels as zha_channels
import homeassistant.components.zha.core.channels.base as base_channels
import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.discovery as disc
import homeassistant.helpers.entity_registry

from .zha_devices_list import DEVICES

NO_TAIL_ID = re.compile("_\\d$")


@pytest.fixture
def channels_mock(zha_device_mock):
    """Channels mock factory."""

    def _mock(
        endpoints,
        ieee="00:11:22:33:44:55:66:77",
        manufacturer="mock manufacturer",
        model="mock model",
        node_desc=b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
    ):
        zha_dev = zha_device_mock(endpoints, ieee, manufacturer, model, node_desc)
        channels = zha_channels.Channels.new(zha_dev)
        return channels

    return _mock


@pytest.mark.parametrize("device", DEVICES)
async def test_devices(
    device, hass, zigpy_device_mock, monkeypatch, zha_device_joined_restored
):
    """Test device discovery."""

    entity_registry = await homeassistant.helpers.entity_registry.async_get_registry(
        hass
    )

    zigpy_device = zigpy_device_mock(
        device["endpoints"],
        "00:11:22:33:44:55:66:77",
        device["manufacturer"],
        device["model"],
        node_descriptor=device["node_descriptor"],
    )

    orig_new_entity = zha_channels.ChannelPool.async_new_entity
    _dispatch = mock.MagicMock(wraps=orig_new_entity)
    try:
        zha_channels.ChannelPool.async_new_entity = lambda *a, **kw: _dispatch(*a, **kw)
        zha_dev = await zha_device_joined_restored(zigpy_device)
        await hass.async_block_till_done()
    finally:
        zha_channels.ChannelPool.async_new_entity = orig_new_entity

    entity_ids = hass.states.async_entity_ids()
    await hass.async_block_till_done()
    zha_entities = {
        ent for ent in entity_ids if ent.split(".")[0] in zha_const.COMPONENTS
    }

    event_channels = {
        ch.id for pool in zha_dev.channels.pools for ch in pool.relay_channels.values()
    }

    entity_map = device["entity_map"]
    assert zha_entities == set(
        [
            e["entity_id"]
            for e in entity_map.values()
            if not e.get("default_match", False)
        ]
    )
    assert event_channels == set(device["event_channels"])

    for call in _dispatch.call_args_list:
        _, component, entity_cls, unique_id, channels = call[0]
        key = (component, unique_id)
        entity_id = entity_registry.async_get_entity_id(component, "zha", unique_id)

        assert key in entity_map
        assert entity_id is not None
        no_tail_id = NO_TAIL_ID.sub("", entity_map[key]["entity_id"])
        assert entity_id.startswith(no_tail_id)
        assert set([ch.name for ch in channels]) == set(entity_map[key]["channels"])
        assert entity_cls.__name__ == entity_map[key]["entity_class"]


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

    ep_channels = mock.MagicMock(spec_set=zha_channels.ChannelPool)
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

    ep_channels = mock.MagicMock(spec_set=zha_channels.ChannelPool)
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

    ep_channels = mock.MagicMock(spec_set=zha_channels.ChannelPool)
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


@pytest.mark.parametrize("device_info", DEVICES)
async def test_discover_endpoint(device_info, channels_mock, hass):
    """Test device discovery."""

    with mock.patch(
        "homeassistant.components.zha.core.channels.Channels.async_new_entity"
    ) as new_ent:
        channels = channels_mock(
            device_info["endpoints"],
            manufacturer=device_info["manufacturer"],
            model=device_info["model"],
            node_desc=device_info["node_descriptor"],
        )

    assert device_info["event_channels"] == sorted(
        [ch.id for pool in channels.pools for ch in pool.relay_channels.values()]
    )
    assert new_ent.call_count == len(
        [
            device_info
            for device_info in device_info["entity_map"].values()
            if not device_info.get("default_match", False)
        ]
    )

    for call_args in new_ent.call_args_list:
        comp, ent_cls, unique_id, channels = call_args[0]
        map_id = (comp, unique_id)
        assert map_id in device_info["entity_map"]
        entity_info = device_info["entity_map"][map_id]
        assert set([ch.name for ch in channels]) == set(entity_info["channels"])
        assert ent_cls.__name__ == entity_info["entity_class"]
