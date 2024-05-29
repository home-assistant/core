"""Test configuration for the ZHA component."""

from collections.abc import Callable, Generator
import itertools
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
import warnings

import pytest
import zigpy
from zigpy.application import ControllerApplication
import zigpy.backups
import zigpy.config
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
import zigpy.device
import zigpy.group
import zigpy.profiles
import zigpy.quirks
import zigpy.state
import zigpy.types
import zigpy.util
from zigpy.zcl.clusters.general import Basic, Groups
from zigpy.zcl.foundation import Status
import zigpy.zdo.types as zdo_t

import homeassistant.components.zha.core.const as zha_const
import homeassistant.components.zha.core.device as zha_core_device
from homeassistant.components.zha.core.gateway import ZHAGateway
from homeassistant.components.zha.core.helpers import get_zha_gateway
from homeassistant.helpers import restore_state
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import patch_cluster as common_patch_cluster

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401

FIXTURE_GRP_ID = 0x1001
FIXTURE_GRP_NAME = "fixture group"
COUNTER_NAMES = ["counter_1", "counter_2", "counter_3"]


@pytest.fixture(scope="module", autouse=True)
def disable_request_retry_delay():
    """Disable ZHA request retrying delay to speed up failures."""

    with patch(
        "homeassistant.components.zha.core.cluster_handlers.RETRYABLE_REQUEST_DECORATOR",
        zigpy.util.retryable_request(tries=3, delay=0),
    ):
        yield


@pytest.fixture(scope="module", autouse=True)
def globally_load_quirks():
    """Load quirks automatically so that ZHA tests run deterministically in isolation.

    If portions of the ZHA test suite that do not happen to load quirks are run
    independently, bugs can emerge that will show up only when more of the test suite is
    run.
    """

    import zhaquirks

    zhaquirks.setup()


class _FakeApp(ControllerApplication):
    async def add_endpoint(self, descriptor: zdo_t.SimpleDescriptor):
        pass

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def force_remove(self, dev: zigpy.device.Device):
        pass

    async def load_network_info(self, *, load_devices: bool = False):
        pass

    async def permit_ncp(self, time_s: int = 60):
        pass

    async def permit_with_link_key(
        self, node: zigpy.types.EUI64, link_key: zigpy.types.KeyData, time_s: int = 60
    ):
        pass

    async def reset_network_info(self):
        pass

    async def send_packet(self, packet: zigpy.types.ZigbeePacket):
        pass

    async def start_network(self):
        pass

    async def write_network_info(
        self, *, network_info: zigpy.state.NetworkInfo, node_info: zigpy.state.NodeInfo
    ) -> None:
        pass

    async def request(
        self,
        device: zigpy.device.Device,
        profile: zigpy.types.uint16_t,
        cluster: zigpy.types.uint16_t,
        src_ep: zigpy.types.uint8_t,
        dst_ep: zigpy.types.uint8_t,
        sequence: zigpy.types.uint8_t,
        data: bytes,
        *,
        expect_reply: bool = True,
        use_ieee: bool = False,
        extended_timeout: bool = False,
    ):
        pass

    async def move_network_to_channel(
        self, new_channel: int, *, num_broadcasts: int = 5
    ) -> None:
        pass


def _wrap_mock_instance(obj: Any) -> MagicMock:
    """Auto-mock every attribute and method in an object."""
    mock = create_autospec(obj, spec_set=True, instance=True)

    for attr_name in dir(obj):
        if attr_name.startswith("__") and attr_name not in {"__getitem__"}:
            continue

        real_attr = getattr(obj, attr_name)
        mock_attr = getattr(mock, attr_name)

        if callable(real_attr) and not hasattr(real_attr, "__aenter__"):
            mock_attr.side_effect = real_attr
        else:
            setattr(mock, attr_name, real_attr)

    return mock


@pytest.fixture
async def zigpy_app_controller():
    """Zigpy ApplicationController fixture."""
    app = _FakeApp(
        {
            zigpy.config.CONF_DATABASE: None,
            zigpy.config.CONF_DEVICE: {zigpy.config.CONF_DEVICE_PATH: "/dev/null"},
            zigpy.config.CONF_STARTUP_ENERGY_SCAN: False,
            zigpy.config.CONF_NWK_BACKUP_ENABLED: False,
            zigpy.config.CONF_TOPO_SCAN_ENABLED: False,
            zigpy.config.CONF_OTA: {
                zigpy.config.CONF_OTA_ENABLED: False,
            },
        }
    )

    app.groups.add_group(FIXTURE_GRP_ID, FIXTURE_GRP_NAME, suppress_event=True)

    app.state.node_info.nwk = 0x0000
    app.state.node_info.ieee = zigpy.types.EUI64.convert("00:15:8d:00:02:32:4f:32")
    app.state.network_info.pan_id = 0x1234
    app.state.network_info.extended_pan_id = app.state.node_info.ieee
    app.state.network_info.channel = 15
    app.state.network_info.network_key.key = zigpy.types.KeyData(range(16))
    app.state.counters = zigpy.state.CounterGroups()
    app.state.counters["ezsp_counters"] = zigpy.state.CounterGroup("ezsp_counters")
    for name in COUNTER_NAMES:
        app.state.counters["ezsp_counters"][name].increment()

    # Create a fake coordinator device
    dev = app.add_device(nwk=app.state.node_info.nwk, ieee=app.state.node_info.ieee)
    dev.node_desc = zdo_t.NodeDescriptor()
    dev.node_desc.logical_type = zdo_t.LogicalType.Coordinator
    dev.manufacturer = "Coordinator Manufacturer"
    dev.model = "Coordinator Model"

    ep = dev.add_endpoint(1)
    ep.add_input_cluster(Basic.cluster_id)
    ep.add_input_cluster(Groups.cluster_id)

    with patch("zigpy.device.Device.request", return_value=[Status.SUCCESS]):
        # The mock wrapping accesses deprecated attributes, so we suppress the warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mock_app = _wrap_mock_instance(app)
            mock_app.backups = _wrap_mock_instance(app.backups)

        yield mock_app


@pytest.fixture(name="config_entry")
async def config_entry_fixture(hass) -> MockConfigEntry:
    """Fixture representing a config entry."""
    return MockConfigEntry(
        version=3,
        domain=zha_const.DOMAIN,
        data={
            zigpy.config.CONF_DEVICE: {zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB0"},
            zha_const.CONF_RADIO_TYPE: "ezsp",
        },
        options={
            zha_const.CUSTOM_CONFIGURATION: {
                zha_const.ZHA_OPTIONS: {
                    zha_const.CONF_ENABLE_ENHANCED_LIGHT_TRANSITION: True,
                    zha_const.CONF_GROUP_MEMBERS_ASSUME_STATE: False,
                },
                zha_const.ZHA_ALARM_OPTIONS: {
                    zha_const.CONF_ALARM_ARM_REQUIRES_CODE: False,
                    zha_const.CONF_ALARM_MASTER_CODE: "4321",
                    zha_const.CONF_ALARM_FAILED_TRIES: 2,
                },
            }
        },
    )


@pytest.fixture
def mock_zigpy_connect(
    zigpy_app_controller: ControllerApplication,
) -> Generator[ControllerApplication, None, None]:
    """Patch the zigpy radio connection with our mock application."""
    with (
        patch(
            "bellows.zigbee.application.ControllerApplication.new",
            return_value=zigpy_app_controller,
        ),
        patch(
            "bellows.zigbee.application.ControllerApplication",
            return_value=zigpy_app_controller,
        ),
    ):
        yield zigpy_app_controller


@pytest.fixture
def setup_zha(
    hass, config_entry: MockConfigEntry, mock_zigpy_connect: ControllerApplication
):
    """Set up ZHA component."""
    zha_config = {zha_const.CONF_ENABLE_QUIRKS: False}

    async def _setup(config=None):
        config_entry.add_to_hass(hass)
        config = config or {}

        status = await async_setup_component(
            hass, zha_const.DOMAIN, {zha_const.DOMAIN: {**zha_config, **config}}
        )
        assert status is True
        await hass.async_block_till_done()

    return _setup


@pytest.fixture
def cluster_handler():
    """ClusterHandler mock factory fixture."""

    def cluster_handler(name: str, cluster_id: int, endpoint_id: int = 1):
        ch = MagicMock()
        ch.name = name
        ch.generic_id = f"cluster_handler_0x{cluster_id:04x}"
        ch.id = f"{endpoint_id}:0x{cluster_id:04x}"
        ch.async_configure = AsyncMock()
        ch.async_initialize = AsyncMock()
        return ch

    return cluster_handler


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
        patch_cluster=True,
        quirk=None,
        attributes=None,
    ):
        """Make a fake device using the specified cluster classes."""
        device = zigpy.device.Device(
            zigpy_app_controller, zigpy.types.EUI64.convert(ieee), nwk
        )
        device.manufacturer = manufacturer
        device.model = model
        device.node_desc = zdo_t.NodeDescriptor.deserialize(node_descriptor)[0]
        device.last_seen = time.time()

        for epid, ep in endpoints.items():
            endpoint = device.add_endpoint(epid)
            endpoint.device_type = ep[SIG_EP_TYPE]
            endpoint.profile_id = ep.get(SIG_EP_PROFILE, 0x0104)
            endpoint.request = AsyncMock()

            for cluster_id in ep.get(SIG_EP_INPUT, []):
                endpoint.add_input_cluster(cluster_id)

            for cluster_id in ep.get(SIG_EP_OUTPUT, []):
                endpoint.add_output_cluster(cluster_id)

        device.status = zigpy.device.Status.ENDPOINTS_INIT

        if quirk:
            device = quirk(zigpy_app_controller, device.ieee, device.nwk, device)
        else:
            # Allow zigpy to apply quirks if we don't pass one explicitly
            device = zigpy.quirks.get_device(device)

        if patch_cluster:
            for endpoint in (ep for epid, ep in device.endpoints.items() if epid):
                endpoint.request = AsyncMock(return_value=[0])
                for cluster in itertools.chain(
                    endpoint.in_clusters.values(), endpoint.out_clusters.values()
                ):
                    common_patch_cluster(cluster)

        if attributes is not None:
            for ep_id, clusters in attributes.items():
                for cluster_name, attrs in clusters.items():
                    cluster = getattr(device.endpoints[ep_id], cluster_name)

                    for name, value in attrs.items():
                        attr_id = cluster.find_attribute(name).id
                        cluster._attr_cache[attr_id] = value

        return device

    return _mock_dev


@patch("homeassistant.components.zha.setup_quirks", MagicMock(return_value=True))
@pytest.fixture
def zha_device_joined(hass, setup_zha):
    """Return a newly joined ZHA device."""
    setup_zha_fixture = setup_zha

    async def _zha_device(zigpy_dev, *, setup_zha: bool = True):
        zigpy_dev.last_seen = time.time()

        if setup_zha:
            await setup_zha_fixture()

        zha_gateway = get_zha_gateway(hass)
        zha_gateway.application_controller.devices[zigpy_dev.ieee] = zigpy_dev
        await zha_gateway.async_device_initialized(zigpy_dev)
        await hass.async_block_till_done()
        return zha_gateway.get_device(zigpy_dev.ieee)

    return _zha_device


@patch("homeassistant.components.zha.setup_quirks", MagicMock(return_value=True))
@pytest.fixture
def zha_device_restored(hass, zigpy_app_controller, setup_zha):
    """Return a restored ZHA device."""
    setup_zha_fixture = setup_zha

    async def _zha_device(zigpy_dev, *, last_seen=None, setup_zha: bool = True):
        zigpy_app_controller.devices[zigpy_dev.ieee] = zigpy_dev

        if last_seen is not None:
            zigpy_dev.last_seen = last_seen

        if setup_zha:
            await setup_zha_fixture()

        zha_gateway = get_zha_gateway(hass)
        return zha_gateway.get_device(zigpy_dev.ieee)

    return _zha_device


@pytest.fixture(params=["zha_device_joined", "zha_device_restored"])
def zha_device_joined_restored(request):
    """Join or restore ZHA device."""
    named_method = request.getfixturevalue(request.param)
    named_method.name = request.param
    return named_method


@pytest.fixture
def zha_device_mock(
    hass, config_entry, zigpy_device_mock
) -> Callable[..., zha_core_device.ZHADevice]:
    """Return a ZHA Device factory."""

    def _zha_device(
        endpoints=None,
        ieee="00:11:22:33:44:55:66:77",
        manufacturer="mock manufacturer",
        model="mock model",
        node_desc=b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
        patch_cluster=True,
    ) -> zha_core_device.ZHADevice:
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
            endpoints, ieee, manufacturer, model, node_desc, patch_cluster=patch_cluster
        )
        return zha_core_device.ZHADevice(
            hass,
            zigpy_device,
            ZHAGateway(hass, {}, config_entry),
        )

    return _zha_device


@pytest.fixture
def hass_disable_services(hass):
    """Mock services."""
    with patch.object(
        hass, "services", MagicMock(has_service=MagicMock(return_value=True))
    ):
        yield hass


@pytest.fixture(autouse=True)
def speed_up_radio_mgr():
    """Speed up the radio manager connection time by removing delays."""
    with patch("homeassistant.components.zha.radio_manager.CONNECT_DELAY_S", 0.00001):
        yield


@pytest.fixture
def network_backup() -> zigpy.backups.NetworkBackup:
    """Real ZHA network backup taken from an active instance."""
    return zigpy.backups.NetworkBackup.from_dict(
        {
            "backup_time": "2022-11-16T03:16:49.427675+00:00",
            "network_info": {
                "extended_pan_id": "2f:73:58:bd:fe:78:91:11",
                "pan_id": "2DB4",
                "nwk_update_id": 0,
                "nwk_manager_id": "0000",
                "channel": 15,
                "channel_mask": [
                    11,
                    12,
                    13,
                    14,
                    15,
                    16,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                ],
                "security_level": 5,
                "network_key": {
                    "key": "4a:c7:9d:50:51:09:16:37:2e:34:66:c6:ed:9b:23:85",
                    "tx_counter": 14131,
                    "rx_counter": 0,
                    "seq": 0,
                    "partner_ieee": "ff:ff:ff:ff:ff:ff:ff:ff",
                },
                "tc_link_key": {
                    "key": "5a:69:67:42:65:65:41:6c:6c:69:61:6e:63:65:30:39",
                    "tx_counter": 0,
                    "rx_counter": 0,
                    "seq": 0,
                    "partner_ieee": "84:ba:20:ff:fe:59:f5:ff",
                },
                "key_table": [],
                "children": [],
                "nwk_addresses": {"cc:cc:cc:ff:fe:e6:8e:ca": "1431"},
                "stack_specific": {
                    "ezsp": {"hashed_tclk": "e9bd3ac165233d95923613c608beb147"}
                },
                "metadata": {
                    "ezsp": {
                        "manufacturer": "",
                        "board": "",
                        "version": "7.1.3.0 build 0",
                        "stack_version": 9,
                        "can_write_custom_eui64": False,
                    }
                },
                "source": "bellows@0.34.2",
            },
            "node_info": {
                "nwk": "0000",
                "ieee": "84:ba:20:ff:fe:59:f5:ff",
                "logical_type": "coordinator",
            },
        }
    )


@pytest.fixture
def core_rs(hass_storage):
    """Core.restore_state fixture."""

    def _storage(entity_id, state, attributes={}):
        now = dt_util.utcnow().isoformat()

        hass_storage[restore_state.STORAGE_KEY] = {
            "version": restore_state.STORAGE_VERSION,
            "key": restore_state.STORAGE_KEY,
            "data": [
                {
                    "state": {
                        "entity_id": entity_id,
                        "state": str(state),
                        "attributes": attributes,
                        "last_changed": now,
                        "last_updated": now,
                        "context": {
                            "id": "3c2243ff5f30447eb12e7348cfd5b8ff",
                            "user_id": None,
                        },
                    },
                    "last_seen": now,
                }
            ],
        }

    return _storage
