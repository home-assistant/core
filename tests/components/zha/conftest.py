"""Test configuration for the ZHA component."""
from unittest import mock

import asynctest
import pytest
import zigpy
from zigpy.application import ControllerApplication
import zigpy.group
import zigpy.types

import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.device as zha_core_device
import homeassistant.components.zha.core.registries as zha_regs
from homeassistant.setup import async_setup_component

from .common import FakeDevice, FakeEndpoint, get_zha_gateway

from tests.common import MockConfigEntry

FIXTURE_GRP_ID = 0x1001
FIXTURE_GRP_NAME = "fixture group"


@pytest.fixture
def zigpy_app_controller():
    """Zigpy ApplicationController fixture."""
    app = mock.MagicMock(spec_set=ControllerApplication)
    app.startup = asynctest.CoroutineMock()
    app.shutdown = asynctest.CoroutineMock()
    groups = zigpy.group.Groups(app)
    groups.add_group(FIXTURE_GRP_ID, FIXTURE_GRP_NAME, suppress_event=True)
    app.configure_mock(groups=groups)
    type(app).ieee = mock.PropertyMock()
    app.ieee.return_value = zigpy.types.EUI64.convert("00:15:8d:00:02:32:4f:32")
    type(app).nwk = mock.PropertyMock(return_value=zigpy.types.NWK(0x0000))
    type(app).devices = mock.PropertyMock(return_value={})
    return app


@pytest.fixture
def zigpy_radio():
    """Zigpy radio mock."""
    radio = mock.MagicMock()
    radio.connect = asynctest.CoroutineMock()
    return radio


@pytest.fixture(name="config_entry")
async def config_entry_fixture(hass):
    """Fixture representing a config entry."""
    entry = MockConfigEntry(
        version=1,
        domain=zha_const.DOMAIN,
        data={
            zha_const.CONF_BAUDRATE: zha_const.DEFAULT_BAUDRATE,
            zha_const.CONF_RADIO_TYPE: "MockRadio",
            zha_const.CONF_USB_PATH: "/dev/ttyUSB0",
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def setup_zha(hass, config_entry, zigpy_app_controller, zigpy_radio):
    """Set up ZHA component."""
    zha_config = {zha_const.CONF_ENABLE_QUIRKS: False}

    radio_details = {
        zha_const.ZHA_GW_RADIO: mock.MagicMock(return_value=zigpy_radio),
        zha_const.CONTROLLER: mock.MagicMock(return_value=zigpy_app_controller),
        zha_const.ZHA_GW_RADIO_DESCRIPTION: "mock radio",
    }

    async def _setup(config=None):
        config = config or {}
        with mock.patch.dict(zha_regs.RADIO_TYPES, {"MockRadio": radio_details}):
            status = await async_setup_component(
                hass, zha_const.DOMAIN, {zha_const.DOMAIN: {**zha_config, **config}}
            )
            assert status is True
            await hass.async_block_till_done()

    return _setup


@pytest.fixture
def channel():
    """Channel mock factory fixture."""

    def channel(name: str, cluster_id: int, endpoint_id: int = 1):
        ch = mock.MagicMock()
        ch.name = name
        ch.generic_id = f"channel_0x{cluster_id:04x}"
        ch.id = f"{endpoint_id}:0x{cluster_id:04x}"
        ch.async_configure = asynctest.CoroutineMock()
        ch.async_initialize = asynctest.CoroutineMock()
        return ch

    return channel


@pytest.fixture
def zigpy_device_mock(zigpy_app_controller):
    """Make a fake device using the specified cluster classes."""

    def _mock_dev(
        endpoints,
        ieee="00:0d:6f:00:0a:90:69:e7",
        manufacturer="FakeManufacturer",
        model="FakeModel",
        node_descriptor=b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
        nwk=0xB79C,
    ):
        """Make a fake device using the specified cluster classes."""
        device = FakeDevice(
            zigpy_app_controller, ieee, manufacturer, model, node_descriptor, nwk=nwk
        )
        for epid, ep in endpoints.items():
            endpoint = FakeEndpoint(manufacturer, model, epid)
            endpoint.device = device
            device.endpoints[epid] = endpoint
            endpoint.device_type = ep["device_type"]
            profile_id = ep.get("profile_id")
            if profile_id:
                endpoint.profile_id = profile_id

            for cluster_id in ep.get("in_clusters", []):
                endpoint.add_input_cluster(cluster_id)

            for cluster_id in ep.get("out_clusters", []):
                endpoint.add_output_cluster(cluster_id)

        return device

    return _mock_dev


@pytest.fixture
def zha_device_joined(hass, setup_zha):
    """Return a newly joined ZHA device."""

    async def _zha_device(zigpy_dev):
        await setup_zha()
        zha_gateway = get_zha_gateway(hass)
        await zha_gateway.async_device_initialized(zigpy_dev)
        await hass.async_block_till_done()
        return zha_gateway.get_device(zigpy_dev.ieee)

    return _zha_device


@pytest.fixture
def zha_device_restored(hass, zigpy_app_controller, setup_zha):
    """Return a restored ZHA device."""

    async def _zha_device(zigpy_dev):
        zigpy_app_controller.devices[zigpy_dev.ieee] = zigpy_dev
        await setup_zha()
        zha_gateway = hass.data[zha_const.DATA_ZHA][zha_const.DATA_ZHA_GATEWAY]
        return zha_gateway.get_device(zigpy_dev.ieee)

    return _zha_device


@pytest.fixture(params=["zha_device_joined", "zha_device_restored"])
def zha_device_joined_restored(request):
    """Join or restore ZHA device."""
    named_method = request.getfixturevalue(request.param)
    named_method.name = request.param
    return named_method


@pytest.fixture
def zha_device_mock(hass, zigpy_device_mock):
    """Return a zha Device factory."""

    def _zha_device(
        endpoints=None,
        ieee="00:11:22:33:44:55:66:77",
        manufacturer="mock manufacturer",
        model="mock model",
        node_desc=b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
    ):
        if endpoints is None:
            endpoints = {
                1: {
                    "in_clusters": [0, 1, 8, 768],
                    "out_clusters": [0x19],
                    "device_type": 0x0105,
                },
                2: {
                    "in_clusters": [0],
                    "out_clusters": [6, 8, 0x19, 768],
                    "device_type": 0x0810,
                },
            }
        zigpy_device = zigpy_device_mock(
            endpoints, ieee, manufacturer, model, node_desc
        )
        zha_device = zha_core_device.ZHADevice(hass, zigpy_device, mock.MagicMock())
        return zha_device

    return _zha_device
