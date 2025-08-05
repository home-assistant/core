"""Test configuration for the ZHA component."""

from collections.abc import Generator
import itertools
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
import warnings

import pytest
import zhaquirks
import zigpy
from zigpy.application import ControllerApplication
import zigpy.backups
import zigpy.config
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
import zigpy.device
import zigpy.group
import zigpy.profiles
from zigpy.profiles import zha
import zigpy.quirks
import zigpy.state
import zigpy.types
import zigpy.util
from zigpy.zcl.clusters.general import Basic, Groups
from zigpy.zcl.foundation import Status
import zigpy.zdo.types as zdo_t

from homeassistant.components.zha import const as zha_const
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import patch_cluster as common_patch_cluster

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401

FIXTURE_GRP_ID = 0x1001
FIXTURE_GRP_NAME = "fixture group"
COUNTER_NAMES = ["counter_1", "counter_2", "counter_3"]


@pytest.fixture(scope="package", autouse=True)
def globally_load_quirks():
    """Load quirks automatically so that ZHA tests run deterministically in isolation.

    If portions of the ZHA test suite that do not happen to load quirks are run
    independently, bugs can emerge that will show up only when more of the test suite is
    run.
    """

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

    def _persist_coordinator_model_strings_in_db(self) -> None:
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
    app.state.node_info.manufacturer = "Coordinator Manufacturer"
    app.state.node_info.model = "Coordinator Model"
    app.state.node_info.version = "7.1.4.0 build 389"
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
    ep.profile_id = zha.PROFILE_ID
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
async def config_entry_fixture() -> MockConfigEntry:
    """Fixture representing a config entry."""
    return MockConfigEntry(
        version=4,
        domain=zha_const.DOMAIN,
        data={
            zigpy.config.CONF_DEVICE: {
                zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB0",
                zigpy.config.CONF_DEVICE_BAUDRATE: 115200,
                zigpy.config.CONF_DEVICE_FLOW_CONTROL: "hardware",
            },
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
) -> Generator[ControllerApplication]:
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
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect: ControllerApplication,
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
