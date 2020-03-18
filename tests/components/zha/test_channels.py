"""Test ZHA Core channels."""
import pytest
import zigpy.types as t

import homeassistant.components.zha.core.channels as channels
import homeassistant.components.zha.core.device as zha_device
import homeassistant.components.zha.core.registries as registries

from .common import get_zha_gateway


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
    cluster_id, bind_count, attrs, hass, zigpy_device_mock, zha_gateway
):
    """Test ZHA core channel configuration for input clusters."""
    zigpy_dev = zigpy_device_mock(
        {1: {"in_clusters": [cluster_id], "out_clusters": [], "device_type": 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )
    zha_dev = zha_device.ZHADevice(hass, zigpy_dev, zha_gateway)

    cluster = zigpy_dev.endpoints[1].in_clusters[cluster_id]
    channel_class = registries.ZIGBEE_CHANNEL_REGISTRY.get(
        cluster_id, channels.AttributeListeningChannel
    )
    channel = channel_class(cluster, zha_dev)

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
    cluster_id, bind_count, zha_gateway, hass, zigpy_device_mock
):
    """Test ZHA core channel configuration for output clusters."""
    zigpy_dev = zigpy_device_mock(
        {1: {"out_clusters": [cluster_id], "in_clusters": [], "device_type": 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )
    zha_dev = zha_device.ZHADevice(hass, zigpy_dev, zha_gateway)

    cluster = zigpy_dev.endpoints[1].out_clusters[cluster_id]
    cluster.bind_only = True
    channel_class = registries.ZIGBEE_CHANNEL_REGISTRY.get(
        cluster_id, channels.AttributeListeningChannel
    )
    channel = channel_class(cluster, zha_dev)

    await channel.async_configure()

    assert cluster.bind.call_count == bind_count
    assert cluster.configure_reporting.call_count == 0


def test_channel_registry():
    """Test ZIGBEE Channel Registry."""
    for (cluster_id, channel) in registries.ZIGBEE_CHANNEL_REGISTRY.items():
        assert isinstance(cluster_id, int)
        assert 0 <= cluster_id <= 0xFFFF
        assert issubclass(channel, channels.ZigbeeChannel)
