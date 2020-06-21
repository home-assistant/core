"""Test zha device discovery."""

import re
from unittest import mock

import pytest
import zigpy.quirks
import zigpy.types
import zigpy.zcl.clusters.closures
import zigpy.zcl.clusters.general
import zigpy.zcl.clusters.security
import zigpy.zcl.foundation as zcl_f

import homeassistant.components.zha.binary_sensor
import homeassistant.components.zha.core.channels as zha_channels
import homeassistant.components.zha.core.channels.base as base_channels
import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.discovery as disc
import homeassistant.components.zha.core.registries as zha_regs
import homeassistant.components.zha.cover
import homeassistant.components.zha.device_tracker
import homeassistant.components.zha.fan
import homeassistant.components.zha.light
import homeassistant.components.zha.lock
import homeassistant.components.zha.sensor
import homeassistant.components.zha.switch
import homeassistant.helpers.entity_registry

from .common import get_zha_gateway
from .zha_devices_list import DEVICES

from tests.async_mock import AsyncMock, patch

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


@patch(
    "zigpy.zcl.clusters.general.Identify.request",
    new=AsyncMock(return_value=[mock.sentinel.data, zcl_f.Status.SUCCESS]),
)
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

    cluster_identify = _get_first_identify_cluster(zigpy_device)
    if cluster_identify:
        cluster_identify.request.reset_mock()

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
    zha_entity_ids = {
        ent for ent in entity_ids if ent.split(".")[0] in zha_const.COMPONENTS
    }

    if cluster_identify:
        called = int(zha_device_joined_restored.name == "zha_device_joined")
        assert cluster_identify.request.call_count == called
        assert cluster_identify.request.await_count == called
        if called:
            assert cluster_identify.request.call_args == mock.call(
                False,
                64,
                (zigpy.types.uint8_t, zigpy.types.uint8_t),
                2,
                0,
                expect_reply=True,
                manufacturer=None,
                tsn=None,
            )

    event_channels = {
        ch.id for pool in zha_dev.channels.pools for ch in pool.client_channels.values()
    }

    entity_map = device["entity_map"]
    assert zha_entity_ids == {
        e["entity_id"] for e in entity_map.values() if not e.get("default_match", False)
    }
    assert event_channels == set(device["event_channels"])

    for call in _dispatch.call_args_list:
        _, component, entity_cls, unique_id, channels = call[0]
        key = (component, unique_id)
        entity_id = entity_registry.async_get_entity_id(component, "zha", unique_id)

        assert key in entity_map
        assert entity_id is not None
        no_tail_id = NO_TAIL_ID.sub("", entity_map[key]["entity_id"])
        assert entity_id.startswith(no_tail_id)
        assert {ch.name for ch in channels} == set(entity_map[key]["channels"])
        assert entity_cls.__name__ == entity_map[key]["entity_class"]


def _get_first_identify_cluster(zigpy_device):
    for endpoint in list(zigpy_device.endpoints.values())[1:]:
        if hasattr(endpoint, "identify"):
            return endpoint.identify


@mock.patch(
    "homeassistant.components.zha.core.discovery.ProbeEndpoint.discover_by_device_type"
)
@mock.patch(
    "homeassistant.components.zha.core.discovery.ProbeEndpoint.discover_by_cluster_id"
)
def test_discover_entities(m1, m2):
    """Test discover endpoint class method."""
    ep_channels = mock.MagicMock()
    disc.PROBE.discover_entities(ep_channels)
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
        return_value=(mock.sentinel.entity_cls, mock.sentinel.claimed)
    )
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ):
        disc.PROBE.discover_by_device_type(ep_channels)
    if hit:
        assert get_entity_mock.call_count == 1
        assert ep_channels.claim_channels.call_count == 1
        assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
        assert ep_channels.async_new_entity.call_count == 1
        assert ep_channels.async_new_entity.call_args[0][0] == component
        assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity_cls


def test_discover_by_device_type_override():
    """Test entity discovery by device type overriding."""

    ep_channels = mock.MagicMock(spec_set=zha_channels.ChannelPool)
    ep_mock = mock.PropertyMock()
    ep_mock.return_value.profile_id = 0x0104
    ep_mock.return_value.device_type = 0x0100
    type(ep_channels).endpoint = ep_mock

    overrides = {ep_channels.unique_id: {"type": zha_const.SWITCH}}
    get_entity_mock = mock.MagicMock(
        return_value=(mock.sentinel.entity_cls, mock.sentinel.claimed)
    )
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ):
        with mock.patch.dict(disc.PROBE._device_configs, overrides, clear=True):
            disc.PROBE.discover_by_device_type(ep_channels)
            assert get_entity_mock.call_count == 1
            assert ep_channels.claim_channels.call_count == 1
            assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
            assert ep_channels.async_new_entity.call_count == 1
            assert ep_channels.async_new_entity.call_args[0][0] == zha_const.SWITCH
            assert (
                ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity_cls
            )


def test_discover_probe_single_cluster():
    """Test entity discovery by single cluster."""

    ep_channels = mock.MagicMock(spec_set=zha_channels.ChannelPool)
    ep_mock = mock.PropertyMock()
    ep_mock.return_value.profile_id = 0x0104
    ep_mock.return_value.device_type = 0x0100
    type(ep_channels).endpoint = ep_mock

    get_entity_mock = mock.MagicMock(
        return_value=(mock.sentinel.entity_cls, mock.sentinel.claimed)
    )
    channel_mock = mock.MagicMock(spec_set=base_channels.ZigbeeChannel)
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ):
        disc.PROBE.probe_single_cluster(zha_const.SWITCH, channel_mock, ep_channels)

    assert get_entity_mock.call_count == 1
    assert ep_channels.claim_channels.call_count == 1
    assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
    assert ep_channels.async_new_entity.call_count == 1
    assert ep_channels.async_new_entity.call_args[0][0] == zha_const.SWITCH
    assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity_cls
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
        [ch.id for pool in channels.pools for ch in pool.client_channels.values()]
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
        assert {ch.name for ch in channels} == set(entity_info["channels"])
        assert ent_cls.__name__ == entity_info["entity_class"]


def _ch_mock(cluster):
    """Return mock of a channel with a cluster."""
    channel = mock.MagicMock()
    type(channel).cluster = mock.PropertyMock(return_value=cluster(mock.MagicMock()))
    return channel


@mock.patch(
    "homeassistant.components.zha.core.discovery.ProbeEndpoint"
    ".handle_on_off_output_cluster_exception",
    new=mock.MagicMock(),
)
@mock.patch(
    "homeassistant.components.zha.core.discovery.ProbeEndpoint.probe_single_cluster"
)
def _test_single_input_cluster_device_class(probe_mock):
    """Test SINGLE_INPUT_CLUSTER_DEVICE_CLASS matching by cluster id or class."""

    door_ch = _ch_mock(zigpy.zcl.clusters.closures.DoorLock)
    cover_ch = _ch_mock(zigpy.zcl.clusters.closures.WindowCovering)
    multistate_ch = _ch_mock(zigpy.zcl.clusters.general.MultistateInput)

    class QuirkedIAS(zigpy.quirks.CustomCluster, zigpy.zcl.clusters.security.IasZone):
        pass

    ias_ch = _ch_mock(QuirkedIAS)

    class _Analog(zigpy.quirks.CustomCluster, zigpy.zcl.clusters.general.AnalogInput):
        pass

    analog_ch = _ch_mock(_Analog)

    ch_pool = mock.MagicMock(spec_set=zha_channels.ChannelPool)
    ch_pool.unclaimed_channels.return_value = [
        door_ch,
        cover_ch,
        multistate_ch,
        ias_ch,
        analog_ch,
    ]

    disc.ProbeEndpoint().discover_by_cluster_id(ch_pool)
    assert probe_mock.call_count == len(ch_pool.unclaimed_channels())
    probes = (
        (zha_const.LOCK, door_ch),
        (zha_const.COVER, cover_ch),
        (zha_const.SENSOR, multistate_ch),
        (zha_const.BINARY_SENSOR, ias_ch),
        (zha_const.SENSOR, analog_ch),
    )
    for call, details in zip(probe_mock.call_args_list, probes):
        component, ch = details
        assert call[0][0] == component
        assert call[0][1] == ch


def test_single_input_cluster_device_class():
    """Test SINGLE_INPUT_CLUSTER_DEVICE_CLASS matching by cluster id or class."""
    _test_single_input_cluster_device_class()


def test_single_input_cluster_device_class_by_cluster_class():
    """Test SINGLE_INPUT_CLUSTER_DEVICE_CLASS matching by cluster id or class."""
    mock_reg = {
        zigpy.zcl.clusters.closures.DoorLock.cluster_id: zha_const.LOCK,
        zigpy.zcl.clusters.closures.WindowCovering.cluster_id: zha_const.COVER,
        zigpy.zcl.clusters.general.AnalogInput: zha_const.SENSOR,
        zigpy.zcl.clusters.general.MultistateInput: zha_const.SENSOR,
        zigpy.zcl.clusters.security.IasZone: zha_const.BINARY_SENSOR,
    }

    with mock.patch.dict(
        zha_regs.SINGLE_INPUT_CLUSTER_DEVICE_CLASS, mock_reg, clear=True
    ):
        _test_single_input_cluster_device_class()


@pytest.mark.parametrize(
    "override, entity_id",
    [
        (None, "light.manufacturer_model_77665544_level_light_color_on_off"),
        ("switch", "switch.manufacturer_model_77665544_on_off"),
    ],
)
async def test_device_override(hass, zigpy_device_mock, setup_zha, override, entity_id):
    """Test device discovery override."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "device_type": 258,
                "endpoint_id": 1,
                "in_clusters": [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                "out_clusters": [25],
                "profile_id": 260,
            }
        },
        "00:11:22:33:44:55:66:77",
        "manufacturer",
        "model",
    )

    if override is not None:
        override = {"device_config": {"00:11:22:33:44:55:66:77-1": {"type": override}}}

    await setup_zha(override)
    assert hass.states.get(entity_id) is None
    zha_gateway = get_zha_gateway(hass)
    await zha_gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is not None


async def test_group_probe_cleanup_called(hass, setup_zha, config_entry):
    """Test cleanup happens when zha is unloaded."""
    await setup_zha()
    disc.GROUP_PROBE.cleanup = mock.Mock(wraps=disc.GROUP_PROBE.cleanup)
    await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    disc.GROUP_PROBE.cleanup.assert_called()
