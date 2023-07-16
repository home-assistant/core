"""Test ZHA device switch."""
from datetime import timedelta
import logging
import time
from unittest import mock
from unittest.mock import patch

import pytest
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl.clusters.general as general
import zigpy.zdo.types as zdo_t

from homeassistant.components.zha.core.const import (
    CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY,
    CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS,
)
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.util.dt as dt_util

from .common import async_enable_traffic, make_zcl_header
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_TYPE

from tests.common import async_fire_time_changed


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only set up the required platform and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
            Platform.BINARY_SENSOR,
        ),
    ):
        yield


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""

    def _dev(with_basic_cluster_handler: bool = True, **kwargs):
        in_clusters = [general.OnOff.cluster_id]
        if with_basic_cluster_handler:
            in_clusters.append(general.Basic.cluster_id)

        endpoints = {
            3: {
                SIG_EP_INPUT: in_clusters,
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
        return zigpy_device_mock(endpoints, **kwargs)

    return _dev


@pytest.fixture
def zigpy_device_mains(zigpy_device_mock):
    """Device tracker zigpy device."""

    def _dev(with_basic_cluster_handler: bool = True):
        in_clusters = [general.OnOff.cluster_id]
        if with_basic_cluster_handler:
            in_clusters.append(general.Basic.cluster_id)

        endpoints = {
            3: {
                SIG_EP_INPUT: in_clusters,
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
        return zigpy_device_mock(
            endpoints, node_descriptor=b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00"
        )

    return _dev


@pytest.fixture
def device_with_basic_cluster_handler(zigpy_device_mains):
    """Return a ZHA device with a basic cluster handler present."""
    return zigpy_device_mains(with_basic_cluster_handler=True)


@pytest.fixture
def device_without_basic_cluster_handler(zigpy_device):
    """Return a ZHA device without a basic cluster handler present."""
    return zigpy_device(with_basic_cluster_handler=False)


@pytest.fixture
async def ota_zha_device(zha_device_restored, zigpy_device_mock):
    """ZHA device with OTA cluster fixture."""
    zigpy_dev = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [general.Ota.cluster_id],
                SIG_EP_TYPE: 0x1234,
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
    "homeassistant.components.zha.core.cluster_handlers.general.BasicClusterHandler.async_initialize",
    new=mock.AsyncMock(),
)
async def test_check_available_success(
    hass: HomeAssistant, device_with_basic_cluster_handler, zha_device_restored
) -> None:
    """Check device availability success on 1st try."""
    zha_device = await zha_device_restored(device_with_basic_cluster_handler)
    await async_enable_traffic(hass, [zha_device])
    basic_ch = device_with_basic_cluster_handler.endpoints[3].basic

    basic_ch.read_attributes.reset_mock()
    device_with_basic_cluster_handler.last_seen = None
    assert zha_device.available is True
    _send_time_changed(hass, zha_device.consider_unavailable_time + 2)
    await hass.async_block_till_done()
    assert zha_device.available is False
    assert basic_ch.read_attributes.await_count == 0

    device_with_basic_cluster_handler.last_seen = (
        time.time() - zha_device.consider_unavailable_time - 2
    )
    _seens = [time.time(), device_with_basic_cluster_handler.last_seen]

    def _update_last_seen(*args, **kwargs):
        device_with_basic_cluster_handler.last_seen = _seens.pop()

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
    "homeassistant.components.zha.core.cluster_handlers.general.BasicClusterHandler.async_initialize",
    new=mock.AsyncMock(),
)
async def test_check_available_unsuccessful(
    hass: HomeAssistant, device_with_basic_cluster_handler, zha_device_restored
) -> None:
    """Check device availability all tries fail."""

    zha_device = await zha_device_restored(device_with_basic_cluster_handler)
    await async_enable_traffic(hass, [zha_device])
    basic_ch = device_with_basic_cluster_handler.endpoints[3].basic

    assert zha_device.available is True
    assert basic_ch.read_attributes.await_count == 0

    device_with_basic_cluster_handler.last_seen = (
        time.time() - zha_device.consider_unavailable_time - 2
    )

    # unsuccessfully ping zigpy device, but zha_device is still available
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

    # not even trying to update, device is unavailable
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert basic_ch.read_attributes.await_count == 2
    assert basic_ch.read_attributes.await_args[0][0] == ["manufacturer"]
    assert zha_device.available is False


@patch(
    "homeassistant.components.zha.core.cluster_handlers.general.BasicClusterHandler.async_initialize",
    new=mock.AsyncMock(),
)
async def test_check_available_no_basic_cluster_handler(
    hass: HomeAssistant,
    device_without_basic_cluster_handler,
    zha_device_restored,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Check device availability for a device without basic cluster."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.zha")

    zha_device = await zha_device_restored(device_without_basic_cluster_handler)
    await async_enable_traffic(hass, [zha_device])

    assert zha_device.available is True

    device_without_basic_cluster_handler.last_seen = (
        time.time() - zha_device.consider_unavailable_time - 2
    )

    assert "does not have a mandatory basic cluster" not in caplog.text
    _send_time_changed(hass, 91)
    await hass.async_block_till_done()
    assert zha_device.available is False
    assert "does not have a mandatory basic cluster" in caplog.text


async def test_ota_sw_version(hass: HomeAssistant, ota_zha_device) -> None:
    """Test device entry gets sw_version updated via OTA cluster handler."""

    ota_ch = ota_zha_device._endpoints[1].client_cluster_handlers["1:0x0019"]
    dev_registry = dr.async_get(hass)
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
    ("device", "last_seen_delta", "is_available"),
    (
        ("zigpy_device", 0, True),
        (
            "zigpy_device",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS + 2,
            True,
        ),
        (
            "zigpy_device",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY - 2,
            True,
        ),
        (
            "zigpy_device",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY + 2,
            False,
        ),
        ("zigpy_device_mains", 0, True),
        (
            "zigpy_device_mains",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS - 2,
            True,
        ),
        (
            "zigpy_device_mains",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_MAINS + 2,
            False,
        ),
        (
            "zigpy_device_mains",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY - 2,
            False,
        ),
        (
            "zigpy_device_mains",
            CONF_DEFAULT_CONSIDER_UNAVAILABLE_BATTERY + 2,
            False,
        ),
    ),
)
async def test_device_restore_availability(
    hass: HomeAssistant,
    request,
    device,
    last_seen_delta,
    is_available,
    zha_device_restored,
) -> None:
    """Test initial availability for restored devices."""

    zigpy_device = request.getfixturevalue(device)()
    zha_device = await zha_device_restored(
        zigpy_device, last_seen=time.time() - last_seen_delta
    )
    entity_id = "switch.fakemanufacturer_fakemodel_switch"

    await hass.async_block_till_done()
    # ensure the switch entity was created
    assert hass.states.get(entity_id).state is not None
    assert zha_device.available is is_available
    if is_available:
        assert hass.states.get(entity_id).state == STATE_OFF
    else:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_device_is_active_coordinator(
    hass: HomeAssistant, zha_device_joined, zigpy_device
) -> None:
    """Test that the current coordinator is uniquely detected."""

    current_coord_dev = zigpy_device(ieee="aa:bb:cc:dd:ee:ff:00:11", nwk=0x0000)
    current_coord_dev.node_desc = current_coord_dev.node_desc.replace(
        logical_type=zdo_t.LogicalType.Coordinator
    )

    old_coord_dev = zigpy_device(ieee="aa:bb:cc:dd:ee:ff:00:12", nwk=0x0000)
    old_coord_dev.node_desc = old_coord_dev.node_desc.replace(
        logical_type=zdo_t.LogicalType.Coordinator
    )

    # The two coordinators have different IEEE addresses
    assert current_coord_dev.ieee != old_coord_dev.ieee

    current_coordinator = await zha_device_joined(current_coord_dev)
    stale_coordinator = await zha_device_joined(old_coord_dev)

    # Ensure the current ApplicationController's IEEE matches our coordinator's
    current_coordinator.gateway.application_controller.state.node_info.ieee = (
        current_coord_dev.ieee
    )

    assert current_coordinator.is_active_coordinator
    assert not stale_coordinator.is_active_coordinator
