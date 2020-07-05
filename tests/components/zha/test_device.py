"""Test zha device switch."""
from datetime import timedelta
import time
from unittest import mock

import pytest
import zigpy.zcl.clusters.general as general

import homeassistant.components.zha.core.device as zha_core_device
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
import homeassistant.helpers.device_registry as ha_dev_reg
import homeassistant.util.dt as dt_util

from .common import async_enable_traffic, make_zcl_header

from tests.async_mock import patch
from tests.common import async_fire_time_changed


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""

    def _dev(with_basic_channel: bool = True):
        in_clusters = [general.OnOff.cluster_id]
        if with_basic_channel:
            in_clusters.append(general.Basic.cluster_id)

        endpoints = {
            3: {"in_clusters": in_clusters, "out_clusters": [], "device_type": 0}
        }
        return zigpy_device_mock(endpoints)

    return _dev


@pytest.fixture
def zigpy_device_mains(zigpy_device_mock):
    """Device tracker zigpy device."""

    def _dev(with_basic_channel: bool = True):
        in_clusters = [general.OnOff.cluster_id]
        if with_basic_channel:
            in_clusters.append(general.Basic.cluster_id)

        endpoints = {
            3: {"in_clusters": in_clusters, "out_clusters": [], "device_type": 0}
        }
        return zigpy_device_mock(
            endpoints, node_descriptor=b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00"
        )

    return _dev


@pytest.fixture
def device_with_basic_channel(zigpy_device_mains):
    """Return a zha device with a basic channel present."""
    return zigpy_device_mains(with_basic_channel=True)


@pytest.fixture
def device_without_basic_channel(zigpy_device):
    """Return a zha device with a basic channel present."""
    return zigpy_device(with_basic_channel=False)


@pytest.fixture
async def ota_zha_device(zha_device_restored, zigpy_device_mock):
    """ZHA device with OTA cluster fixture."""
    zigpy_dev = zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.Basic.cluster_id],
                "out_clusters": [general.Ota.cluster_id],
                "device_type": 0x1234,
            }
        },
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
    )

    zha_device = await zha_device_restored(zigpy_dev)
    return zha_device


def _send_time_changed(hass, seconds):
    """Send a time changed event."""
    now = dt_util.utcnow() + timedelta(seconds=seconds)
    async_fire_time_changed(hass, now)


@patch(
    "homeassistant.components.zha.core.channels.general.BasicChannel.async_initialize",
    new=mock.MagicMock(),
)
async def test_check_available_success(
    hass, device_with_basic_channel, zha_device_restored
):
    """Check device availability success on 1st try."""

    # pylint: disable=protected-access
    zha_device = await zha_device_restored(device_with_basic_channel)
    await async_enable_traffic(hass, [zha_device])
    basic_ch = device_with_basic_channel.endpoints[3].basic

    basic_ch.read_attributes.reset_mock()
    device_with_basic_channel.last_seen = None
    assert zha_device.available is True
    _send_time_changed(hass, zha_core_device.CONSIDER_UNAVAILABLE_MAINS + 2)
    await hass.async_block_till_done()
    assert zha_device.available is False
    assert basic_ch.read_attributes.await_count == 0

    device_with_basic_channel.last_seen = (
        time.time() - zha_core_device.CONSIDER_UNAVAILABLE_MAINS - 2
    )
    _seens = [time.time(), device_with_basic_channel.last_seen]

    def _update_last_seen(*args, **kwargs):
        device_with_basic_channel.last_seen = _seens.pop()

    basic_ch.read_attributes.side_effect = _update_last_seen

    # successfully ping zigpy device, but zha_device is not yet available
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 1
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is False

    # There was traffic from the device: pings, but not yet available
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 2
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is False

    # There was traffic from the device: don't try to ping, marked as available
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 2
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is True


@patch(
    "homeassistant.components.zha.core.channels.general.BasicChannel.async_initialize",
    new=mock.MagicMock(),
)
async def test_check_available_unsuccessful(
    hass, device_with_basic_channel, zha_device_restored
):
    """Check device availability all tries fail."""

    # pylint: disable=protected-access
    zha_device = await zha_device_restored(device_with_basic_channel)
    await async_enable_traffic(hass, [zha_device])
    basic_ch = device_with_basic_channel.endpoints[3].basic

    assert zha_device.available is True
    assert basic_ch.read_attributes.await_count == 0

    device_with_basic_channel.last_seen = (
        time.time() - zha_core_device.CONSIDER_UNAVAILABLE_MAINS - 2
    )

    # unsuccessfuly ping zigpy device, but zha_device is still available
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 1
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is True

    # still no traffic, but zha_device is still available
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 2
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is True

    # not even trying to update, device is unavailble
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 2
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is False


@patch(
    "homeassistant.components.zha.core.channels.general.BasicChannel.async_initialize",
    new=mock.MagicMock(),
)
async def test_check_available_no_basic_channel(
    hass, device_without_basic_channel, zha_device_restored, caplog
):
    """Check device availability for a device without basic cluster."""

    # pylint: disable=protected-access
    zha_device = await zha_device_restored(device_without_basic_channel)
    await async_enable_traffic(hass, [zha_device])

    assert zha_device.available is True

    device_without_basic_channel.last_seen = (
        time.time() - zha_core_device.CONSIDER_UNAVAILABLE_BATTERY - 2
    )

    assert "does not have a mandatory basic cluster" not in caplog.text
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert zha_device.available is False
    assert "does not have a mandatory basic cluster" in caplog.text


async def test_ota_sw_version(hass, ota_zha_device):
    """Test device entry gets sw_version updated via OTA channel."""

    ota_ch = ota_zha_device.channels.pools[0].client_channels["1:0x0019"]
    dev_registry = await ha_dev_reg.async_get_registry(hass)
    entry = dev_registry.async_get(ota_zha_device.device_id)
    assert entry.sw_version is None

    cluster = ota_ch.cluster
    hdr = make_zcl_header(1, global_command=False)
    sw_version = 0x2345
    cluster.handle_message(hdr, [1, 2, 3, sw_version, None])
    await hass.async_block_till_done()
    entry = dev_registry.async_get(ota_zha_device.device_id)
    assert int(entry.sw_version, base=16) == sw_version


@pytest.mark.parametrize(
    "device, last_seen_delta, is_available",
    (
        ("zigpy_device", 0, True),
        ("zigpy_device", zha_core_device.CONSIDER_UNAVAILABLE_MAINS + 2, True,),
        ("zigpy_device", zha_core_device.CONSIDER_UNAVAILABLE_BATTERY - 2, True,),
        ("zigpy_device", zha_core_device.CONSIDER_UNAVAILABLE_BATTERY + 2, False,),
        ("zigpy_device_mains", 0, True),
        ("zigpy_device_mains", zha_core_device.CONSIDER_UNAVAILABLE_MAINS - 2, True,),
        ("zigpy_device_mains", zha_core_device.CONSIDER_UNAVAILABLE_MAINS + 2, False,),
        (
            "zigpy_device_mains",
            zha_core_device.CONSIDER_UNAVAILABLE_BATTERY - 2,
            False,
        ),
        (
            "zigpy_device_mains",
            zha_core_device.CONSIDER_UNAVAILABLE_BATTERY + 2,
            False,
        ),
    ),
)
async def test_device_restore_availability(
    hass, request, device, last_seen_delta, is_available, zha_device_restored
):
    """Test initial availability for restored devices."""

    zigpy_device = request.getfixturevalue(device)()
    zha_device = await zha_device_restored(
        zigpy_device, last_seen=time.time() - last_seen_delta
    )
    entity_id = "switch.fakemanufacturer_fakemodel_e769900a_on_off"

    await hass.async_block_till_done()
    # ensure the switch entity was created
    assert hass.states.get(entity_id).state is not None
    assert zha_device.available is is_available
    if is_available:
        assert hass.states.get(entity_id).state == STATE_OFF
    else:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
