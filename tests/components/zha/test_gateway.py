"""Test ZHA Gateway."""
import pytest
import zigpy.profiles.zha as zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.lighting as lighting

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN

from .common import async_enable_traffic, get_zha_gateway

IEEE_GROUPABLE_DEVICE = "01:2d:6f:00:0a:90:69:e8"
IEEE_GROUPABLE_DEVICE2 = "02:2d:6f:00:0a:90:69:e8"


@pytest.fixture
def zigpy_dev_basic(zigpy_device_mock):
    """Zigpy device with just a basic cluster."""
    return zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.Basic.cluster_id],
                "out_clusters": [],
                "device_type": 0,
            }
        }
    )


@pytest.fixture
async def zha_dev_basic(hass, zha_device_restored, zigpy_dev_basic):
    """ZHA device with just a basic cluster."""

    zha_device = await zha_device_restored(zigpy_dev_basic)
    return zha_device


@pytest.fixture
async def coordinator(hass, zigpy_device_mock, zha_device_joined):
    """Test zha light platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [],
                "out_clusters": [],
                "device_type": zha.DeviceType.COLOR_DIMMABLE_LIGHT,
            }
        },
        ieee="00:15:8d:00:02:32:4f:32",
        nwk=0x0000,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.set_available(True)
    return zha_device


@pytest.fixture
async def device_light_1(hass, zigpy_device_mock, zha_device_joined):
    """Test zha light platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [
                    general.OnOff.cluster_id,
                    general.LevelControl.cluster_id,
                    lighting.Color.cluster_id,
                    general.Groups.cluster_id,
                ],
                "out_clusters": [],
                "device_type": zha.DeviceType.COLOR_DIMMABLE_LIGHT,
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.set_available(True)
    return zha_device


@pytest.fixture
async def device_light_2(hass, zigpy_device_mock, zha_device_joined):
    """Test zha light platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [
                    general.OnOff.cluster_id,
                    general.LevelControl.cluster_id,
                    lighting.Color.cluster_id,
                    general.Groups.cluster_id,
                ],
                "out_clusters": [],
                "device_type": zha.DeviceType.COLOR_DIMMABLE_LIGHT,
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE2,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.set_available(True)
    return zha_device


async def test_device_left(hass, zigpy_dev_basic, zha_dev_basic):
    """Device leaving the network should become unavailable."""

    assert zha_dev_basic.available is False

    await async_enable_traffic(hass, [zha_dev_basic])
    assert zha_dev_basic.available is True

    get_zha_gateway(hass).device_left(zigpy_dev_basic)
    assert zha_dev_basic.available is False


async def test_create_group(hass, device_light_1, device_light_2, coordinator):
    """Test creating a group with 2 members."""
    zha_gateway = get_zha_gateway(hass)
    assert zha_gateway is not None
    zha_gateway.coordinator_zha_device = coordinator
    coordinator._zha_gateway = zha_gateway
    device_light_1._zha_gateway = zha_gateway
    device_light_2._zha_gateway = zha_gateway
    member_ieee_addresses = [device_light_1.ieee, device_light_2.ieee]
    zha_group = await zha_gateway.async_create_zigpy_group(
        "Test Group", member_ieee_addresses
    )
    await hass.async_block_till_done()

    assert zha_group is not None
    assert zha_group.entity_domain == LIGHT_DOMAIN
    assert len(zha_group.members) == 2
    for member in zha_group.members:
        assert member.ieee in member_ieee_addresses

    assert hass.states.get("light.test_group_group_0x0001") is not None
