"""Test ZHA Core channels."""
import asyncio
from unittest import mock

import pytest
import zigpy.types as t
import zigpy.zcl.clusters

import homeassistant.components.zha.core.channels as zha_channels
import homeassistant.components.zha.core.channels.base as base_channels
import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.registries as registries

from .common import get_zha_gateway, make_zcl_header

import tests.async_mock


@pytest.fixture
def ieee():
    """IEEE fixture."""
    return t.EUI64.deserialize(b"ieeeaddr")[0]


@pytest.fixture
def nwk():
    """NWK fixture."""
    return t.NWK(0xBEEF)


@pytest.fixture
async def zha_gateway(hass, setup_zha):
    """Return ZhaGateway fixture."""
    await setup_zha()
    return get_zha_gateway(hass)


@pytest.fixture
def channel_pool():
    """Endpoint Channels fixture."""
    ch_pool_mock = mock.MagicMock(spec_set=zha_channels.ChannelPool)
    type(ch_pool_mock).skip_configuration = mock.PropertyMock(return_value=False)
    ch_pool_mock.id = 1
    return ch_pool_mock


@pytest.fixture
def poll_control_ch(channel_pool, zigpy_device_mock):
    """Poll control channel fixture."""
    cluster_id = zigpy.zcl.clusters.general.PollControl.cluster_id
    zigpy_dev = zigpy_device_mock(
        {1: {"in_clusters": [cluster_id], "out_clusters": [], "device_type": 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )

    cluster = zigpy_dev.endpoints[1].in_clusters[cluster_id]
    channel_class = registries.ZIGBEE_CHANNEL_REGISTRY.get(cluster_id)
    return channel_class(cluster, channel_pool)


@pytest.fixture
async def poll_control_device(zha_device_restored, zigpy_device_mock):
    """Poll control device fixture."""
    cluster_id = zigpy.zcl.clusters.general.PollControl.cluster_id
    zigpy_dev = zigpy_device_mock(
        {1: {"in_clusters": [cluster_id], "out_clusters": [], "device_type": 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )

    zha_device = await zha_device_restored(zigpy_dev)
    return zha_device


@pytest.mark.parametrize(
    "cluster_id, bind_count, attrs",
    [
        (0x0000, 1, {}),
        (0x0001, 1, {"battery_voltage", "battery_percentage_remaining"}),
        (0x0003, 1, {}),
        (0x0004, 1, {}),
        (0x0005, 1, {}),
        (0x0006, 1, {"on_off"}),
        (0x0007, 1, {}),
        (0x0008, 1, {"current_level"}),
        (0x0009, 1, {}),
        (0x000C, 1, {"present_value"}),
        (0x000D, 1, {"present_value"}),
        (0x000E, 1, {"present_value"}),
        (0x000D, 1, {"present_value"}),
        (0x0010, 1, {"present_value"}),
        (0x0011, 1, {"present_value"}),
        (0x0012, 1, {"present_value"}),
        (0x0013, 1, {"present_value"}),
        (0x0014, 1, {"present_value"}),
        (0x0015, 1, {}),
        (0x0016, 1, {}),
        (0x0019, 1, {}),
        (0x001A, 1, {}),
        (0x001B, 1, {}),
        (0x0020, 1, {}),
        (0x0021, 1, {}),
        (0x0101, 1, {"lock_state"}),
        (0x0202, 1, {"fan_mode"}),
        (0x0300, 1, {"current_x", "current_y", "color_temperature"}),
        (0x0400, 1, {"measured_value"}),
        (0x0401, 1, {"level_status"}),
        (0x0402, 1, {"measured_value"}),
        (0x0403, 1, {"measured_value"}),
        (0x0404, 1, {"measured_value"}),
        (0x0405, 1, {"measured_value"}),
        (0x0406, 1, {"occupancy"}),
        (0x0702, 1, {"instantaneous_demand"}),
        (0x0B04, 1, {"active_power"}),
        (0x1000, 1, {}),
    ],
)
async def test_in_channel_config(
    cluster_id, bind_count, attrs, channel_pool, zigpy_device_mock, zha_gateway
):
    """Test ZHA core channel configuration for input clusters."""
    zigpy_dev = zigpy_device_mock(
        {1: {"in_clusters": [cluster_id], "out_clusters": [], "device_type": 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )

    cluster = zigpy_dev.endpoints[1].in_clusters[cluster_id]
    channel_class = registries.ZIGBEE_CHANNEL_REGISTRY.get(
        cluster_id, base_channels.ZigbeeChannel
    )
    channel = channel_class(cluster, channel_pool)

    await channel.async_configure()

    assert cluster.bind.call_count == bind_count
    assert cluster.configure_reporting.call_count == len(attrs)
    reported_attrs = {attr[0][0] for attr in cluster.configure_reporting.call_args_list}
    assert set(attrs) == reported_attrs


@pytest.mark.parametrize(
    "cluster_id, bind_count",
    [
        (0x0000, 1),
        (0x0001, 1),
        (0x0003, 1),
        (0x0004, 1),
        (0x0005, 1),
        (0x0006, 1),
        (0x0007, 1),
        (0x0008, 1),
        (0x0009, 1),
        (0x0015, 1),
        (0x0016, 1),
        (0x0019, 1),
        (0x001A, 1),
        (0x001B, 1),
        (0x0020, 1),
        (0x0021, 1),
        (0x0101, 1),
        (0x0202, 1),
        (0x0300, 1),
        (0x0400, 1),
        (0x0402, 1),
        (0x0403, 1),
        (0x0405, 1),
        (0x0406, 1),
        (0x0702, 1),
        (0x0B04, 1),
        (0x1000, 1),
    ],
)
async def test_out_channel_config(
    cluster_id, bind_count, channel_pool, zigpy_device_mock, zha_gateway
):
    """Test ZHA core channel configuration for output clusters."""
    zigpy_dev = zigpy_device_mock(
        {1: {"out_clusters": [cluster_id], "in_clusters": [], "device_type": 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )

    cluster = zigpy_dev.endpoints[1].out_clusters[cluster_id]
    cluster.bind_only = True
    channel_class = registries.ZIGBEE_CHANNEL_REGISTRY.get(
        cluster_id, base_channels.ZigbeeChannel
    )
    channel = channel_class(cluster, channel_pool)

    await channel.async_configure()

    assert cluster.bind.call_count == bind_count
    assert cluster.configure_reporting.call_count == 0


def test_channel_registry():
    """Test ZIGBEE Channel Registry."""
    for (cluster_id, channel) in registries.ZIGBEE_CHANNEL_REGISTRY.items():
        assert isinstance(cluster_id, int)
        assert 0 <= cluster_id <= 0xFFFF
        assert issubclass(channel, base_channels.ZigbeeChannel)


def test_epch_unclaimed_channels(channel):
    """Test unclaimed channels."""

    ch_1 = channel(zha_const.CHANNEL_ON_OFF, 6)
    ch_2 = channel(zha_const.CHANNEL_LEVEL, 8)
    ch_3 = channel(zha_const.CHANNEL_COLOR, 768)

    ep_channels = zha_channels.ChannelPool(
        mock.MagicMock(spec_set=zha_channels.Channels), mock.sentinel.ep
    )
    all_channels = {ch_1.id: ch_1, ch_2.id: ch_2, ch_3.id: ch_3}
    with mock.patch.dict(ep_channels.all_channels, all_channels, clear=True):
        available = ep_channels.unclaimed_channels()
        assert ch_1 in available
        assert ch_2 in available
        assert ch_3 in available

        ep_channels.claimed_channels[ch_2.id] = ch_2
        available = ep_channels.unclaimed_channels()
        assert ch_1 in available
        assert ch_2 not in available
        assert ch_3 in available

        ep_channels.claimed_channels[ch_1.id] = ch_1
        available = ep_channels.unclaimed_channels()
        assert ch_1 not in available
        assert ch_2 not in available
        assert ch_3 in available

        ep_channels.claimed_channels[ch_3.id] = ch_3
        available = ep_channels.unclaimed_channels()
        assert ch_1 not in available
        assert ch_2 not in available
        assert ch_3 not in available


def test_epch_claim_channels(channel):
    """Test channel claiming."""

    ch_1 = channel(zha_const.CHANNEL_ON_OFF, 6)
    ch_2 = channel(zha_const.CHANNEL_LEVEL, 8)
    ch_3 = channel(zha_const.CHANNEL_COLOR, 768)

    ep_channels = zha_channels.ChannelPool(
        mock.MagicMock(spec_set=zha_channels.Channels), mock.sentinel.ep
    )
    all_channels = {ch_1.id: ch_1, ch_2.id: ch_2, ch_3.id: ch_3}
    with mock.patch.dict(ep_channels.all_channels, all_channels, clear=True):
        assert ch_1.id not in ep_channels.claimed_channels
        assert ch_2.id not in ep_channels.claimed_channels
        assert ch_3.id not in ep_channels.claimed_channels

        ep_channels.claim_channels([ch_2])
        assert ch_1.id not in ep_channels.claimed_channels
        assert ch_2.id in ep_channels.claimed_channels
        assert ep_channels.claimed_channels[ch_2.id] is ch_2
        assert ch_3.id not in ep_channels.claimed_channels

        ep_channels.claim_channels([ch_3, ch_1])
        assert ch_1.id in ep_channels.claimed_channels
        assert ep_channels.claimed_channels[ch_1.id] is ch_1
        assert ch_2.id in ep_channels.claimed_channels
        assert ep_channels.claimed_channels[ch_2.id] is ch_2
        assert ch_3.id in ep_channels.claimed_channels
        assert ep_channels.claimed_channels[ch_3.id] is ch_3
        assert "1:0x0300" in ep_channels.claimed_channels


@mock.patch(
    "homeassistant.components.zha.core.channels.ChannelPool.add_client_channels"
)
@mock.patch(
    "homeassistant.components.zha.core.discovery.PROBE.discover_entities",
    mock.MagicMock(),
)
def test_ep_channels_all_channels(m1, zha_device_mock):
    """Test EndpointChannels adding all channels."""
    zha_device = zha_device_mock(
        {
            1: {"in_clusters": [0, 1, 6, 8], "out_clusters": [], "device_type": 0x0000},
            2: {
                "in_clusters": [0, 1, 6, 8, 768],
                "out_clusters": [],
                "device_type": 0x0000,
            },
        }
    )
    channels = zha_channels.Channels(zha_device)

    ep_channels = zha_channels.ChannelPool.new(channels, 1)
    assert "1:0x0000" in ep_channels.all_channels
    assert "1:0x0001" in ep_channels.all_channels
    assert "1:0x0006" in ep_channels.all_channels
    assert "1:0x0008" in ep_channels.all_channels
    assert "1:0x0300" not in ep_channels.all_channels
    assert "2:0x0000" not in ep_channels.all_channels
    assert "2:0x0001" not in ep_channels.all_channels
    assert "2:0x0006" not in ep_channels.all_channels
    assert "2:0x0008" not in ep_channels.all_channels
    assert "2:0x0300" not in ep_channels.all_channels

    channels = zha_channels.Channels(zha_device)
    ep_channels = zha_channels.ChannelPool.new(channels, 2)
    assert "1:0x0000" not in ep_channels.all_channels
    assert "1:0x0001" not in ep_channels.all_channels
    assert "1:0x0006" not in ep_channels.all_channels
    assert "1:0x0008" not in ep_channels.all_channels
    assert "1:0x0300" not in ep_channels.all_channels
    assert "2:0x0000" in ep_channels.all_channels
    assert "2:0x0001" in ep_channels.all_channels
    assert "2:0x0006" in ep_channels.all_channels
    assert "2:0x0008" in ep_channels.all_channels
    assert "2:0x0300" in ep_channels.all_channels


@mock.patch(
    "homeassistant.components.zha.core.channels.ChannelPool.add_client_channels"
)
@mock.patch(
    "homeassistant.components.zha.core.discovery.PROBE.discover_entities",
    mock.MagicMock(),
)
def test_channel_power_config(m1, zha_device_mock):
    """Test that channels only get a single power channel."""
    in_clusters = [0, 1, 6, 8]
    zha_device = zha_device_mock(
        {
            1: {"in_clusters": in_clusters, "out_clusters": [], "device_type": 0x0000},
            2: {
                "in_clusters": [*in_clusters, 768],
                "out_clusters": [],
                "device_type": 0x0000,
            },
        }
    )
    channels = zha_channels.Channels.new(zha_device)
    pools = {pool.id: pool for pool in channels.pools}
    assert "1:0x0000" in pools[1].all_channels
    assert "1:0x0001" in pools[1].all_channels
    assert "1:0x0006" in pools[1].all_channels
    assert "1:0x0008" in pools[1].all_channels
    assert "1:0x0300" not in pools[1].all_channels
    assert "2:0x0000" in pools[2].all_channels
    assert "2:0x0001" not in pools[2].all_channels
    assert "2:0x0006" in pools[2].all_channels
    assert "2:0x0008" in pools[2].all_channels
    assert "2:0x0300" in pools[2].all_channels

    zha_device = zha_device_mock(
        {
            1: {"in_clusters": [], "out_clusters": [], "device_type": 0x0000},
            2: {"in_clusters": in_clusters, "out_clusters": [], "device_type": 0x0000},
        }
    )
    channels = zha_channels.Channels.new(zha_device)
    pools = {pool.id: pool for pool in channels.pools}
    assert "1:0x0001" not in pools[1].all_channels
    assert "2:0x0001" in pools[2].all_channels

    zha_device = zha_device_mock(
        {2: {"in_clusters": in_clusters, "out_clusters": [], "device_type": 0x0000}}
    )
    channels = zha_channels.Channels.new(zha_device)
    pools = {pool.id: pool for pool in channels.pools}
    assert "2:0x0001" in pools[2].all_channels


async def test_ep_channels_configure(channel):
    """Test unclaimed channels."""

    ch_1 = channel(zha_const.CHANNEL_ON_OFF, 6)
    ch_2 = channel(zha_const.CHANNEL_LEVEL, 8)
    ch_3 = channel(zha_const.CHANNEL_COLOR, 768)
    ch_3.async_configure = tests.async_mock.AsyncMock(side_effect=asyncio.TimeoutError)
    ch_3.async_initialize = tests.async_mock.AsyncMock(side_effect=asyncio.TimeoutError)
    ch_4 = channel(zha_const.CHANNEL_ON_OFF, 6)
    ch_5 = channel(zha_const.CHANNEL_LEVEL, 8)
    ch_5.async_configure = tests.async_mock.AsyncMock(side_effect=asyncio.TimeoutError)
    ch_5.async_initialize = tests.async_mock.AsyncMock(side_effect=asyncio.TimeoutError)

    channels = mock.MagicMock(spec_set=zha_channels.Channels)
    type(channels).semaphore = mock.PropertyMock(return_value=asyncio.Semaphore(3))
    ep_channels = zha_channels.ChannelPool(channels, mock.sentinel.ep)

    claimed = {ch_1.id: ch_1, ch_2.id: ch_2, ch_3.id: ch_3}
    client_chans = {ch_4.id: ch_4, ch_5.id: ch_5}

    with mock.patch.dict(ep_channels.claimed_channels, claimed, clear=True):
        with mock.patch.dict(ep_channels.client_channels, client_chans, clear=True):
            await ep_channels.async_configure()
            await ep_channels.async_initialize(mock.sentinel.from_cache)

    for ch in [*claimed.values(), *client_chans.values()]:
        assert ch.async_initialize.call_count == 1
        assert ch.async_initialize.await_count == 1
        assert ch.async_initialize.call_args[0][0] is mock.sentinel.from_cache
        assert ch.async_configure.call_count == 1
        assert ch.async_configure.await_count == 1

    assert ch_3.warning.call_count == 2
    assert ch_5.warning.call_count == 2


async def test_poll_control_configure(poll_control_ch):
    """Test poll control channel configuration."""
    await poll_control_ch.async_configure()
    assert poll_control_ch.cluster.write_attributes.call_count == 1
    assert poll_control_ch.cluster.write_attributes.call_args[0][0] == {
        "checkin_interval": poll_control_ch.CHECKIN_INTERVAL
    }


async def test_poll_control_checkin_response(poll_control_ch):
    """Test poll control channel checkin response."""
    rsp_mock = tests.async_mock.AsyncMock()
    set_interval_mock = tests.async_mock.AsyncMock()
    cluster = poll_control_ch.cluster
    patch_1 = mock.patch.object(cluster, "checkin_response", rsp_mock)
    patch_2 = mock.patch.object(cluster, "set_long_poll_interval", set_interval_mock)

    with patch_1, patch_2:
        await poll_control_ch.check_in_response(33)

    assert rsp_mock.call_count == 1
    assert set_interval_mock.call_count == 1

    await poll_control_ch.check_in_response(33)
    assert cluster.endpoint.request.call_count == 2
    assert cluster.endpoint.request.await_count == 2
    assert cluster.endpoint.request.call_args_list[0][0][1] == 33
    assert cluster.endpoint.request.call_args_list[0][0][0] == 0x0020
    assert cluster.endpoint.request.call_args_list[1][0][0] == 0x0020


async def test_poll_control_cluster_command(hass, poll_control_device):
    """Test poll control channel response to cluster command."""
    checkin_mock = tests.async_mock.AsyncMock()
    poll_control_ch = poll_control_device.channels.pools[0].all_channels["1:0x0020"]
    cluster = poll_control_ch.cluster

    events = []
    hass.bus.async_listen("zha_event", lambda x: events.append(x))
    await hass.async_block_till_done()

    with mock.patch.object(poll_control_ch, "check_in_response", checkin_mock):
        tsn = 22
        hdr = make_zcl_header(0, global_command=False, tsn=tsn)
        assert not events
        cluster.handle_message(
            hdr, [mock.sentinel.args, mock.sentinel.args2, mock.sentinel.args3]
        )
        await hass.async_block_till_done()

    assert checkin_mock.call_count == 1
    assert checkin_mock.await_count == 1
    assert checkin_mock.await_args[0][0] == tsn
    assert len(events) == 1
    data = events[0].data
    assert data["command"] == "checkin"
    assert data["args"][0] is mock.sentinel.args
    assert data["args"][1] is mock.sentinel.args2
    assert data["args"][2] is mock.sentinel.args3
    assert data["unique_id"] == "00:11:22:33:44:55:66:77:1:0x0020"
