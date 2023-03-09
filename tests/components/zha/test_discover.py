"""Test ZHA device discovery."""
import re
from unittest import mock
from unittest.mock import AsyncMock, Mock, patch

import pytest
from zigpy.const import SIG_ENDPOINTS, SIG_MANUFACTURER, SIG_MODEL, SIG_NODE_DESC
import zigpy.profiles.zha
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
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .common import get_zha_gateway
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
from .zha_devices_list import (
    DEV_SIG_CHANNELS,
    DEV_SIG_ENT_MAP,
    DEV_SIG_ENT_MAP_CLASS,
    DEV_SIG_ENT_MAP_ID,
    DEV_SIG_EVT_CHANNELS,
    DEVICES,
)

NO_TAIL_ID = re.compile("_\\d$")
UNIQUE_ID_HD = re.compile(r"^(([\da-fA-F]{2}:){7}[\da-fA-F]{2}-\d{1,3})", re.X)

IGNORE_SUFFIXES = [
    zigpy.zcl.clusters.general.OnOff.StartUpOnOff.__name__,
    "on_off_transition_time",
    "on_level",
    "on_transition_time",
    "off_transition_time",
    "default_move_rate",
    "start_up_current_level",
]


def contains_ignored_suffix(unique_id: str) -> bool:
    """Return true if the unique_id ends with an ignored suffix."""
    for suffix in IGNORE_SUFFIXES:
        if suffix.lower() in unique_id.lower():
            return True
    return False


@pytest.fixture
def channels_mock(zha_device_mock):
    """Channels mock factory."""

    def _mock(
        endpoints,
        ieee="00:11:22:33:44:55:66:77",
        manufacturer="mock manufacturer",
        model="mock model",
        node_desc=b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00",
        patch_cluster=False,
    ):
        zha_dev = zha_device_mock(
            endpoints, ieee, manufacturer, model, node_desc, patch_cluster=patch_cluster
        )
        channels = zha_channels.Channels.new(zha_dev)
        return channels

    return _mock


@patch(
    "zigpy.zcl.clusters.general.Identify.request",
    new=AsyncMock(return_value=[mock.sentinel.data, zcl_f.Status.SUCCESS]),
)
# We do this here because we are testing ZHA discovery logic. Point being we want to ensure that
# all discovered entities are dispatched for creation. In order to test this we need the entities
# added to HA. So we ensure that they are all enabled even though they won't necessarily be in reality
# at runtime
@patch(
    "homeassistant.components.zha.entity.ZhaEntity.entity_registry_enabled_default",
    new=Mock(return_value=True),
)
@pytest.mark.parametrize("device", DEVICES)
async def test_devices(
    device,
    hass_disable_services,
    zigpy_device_mock,
    zha_device_joined_restored,
) -> None:
    """Test device discovery."""
    entity_registry = er.async_get(hass_disable_services)

    zigpy_device = zigpy_device_mock(
        device[SIG_ENDPOINTS],
        "00:11:22:33:44:55:66:77",
        device[SIG_MANUFACTURER],
        device[SIG_MODEL],
        node_descriptor=device[SIG_NODE_DESC],
        patch_cluster=False,
    )

    cluster_identify = _get_first_identify_cluster(zigpy_device)
    if cluster_identify:
        cluster_identify.request.reset_mock()

    orig_new_entity = zha_channels.ChannelPool.async_new_entity
    _dispatch = mock.MagicMock(wraps=orig_new_entity)
    try:
        zha_channels.ChannelPool.async_new_entity = lambda *a, **kw: _dispatch(*a, **kw)
        zha_dev = await zha_device_joined_restored(zigpy_device)
        await hass_disable_services.async_block_till_done()
    finally:
        zha_channels.ChannelPool.async_new_entity = orig_new_entity

    if cluster_identify:
        called = int(zha_device_joined_restored.name == "zha_device_joined")
        assert cluster_identify.request.call_count == called
        assert cluster_identify.request.await_count == called
        if called:
            assert cluster_identify.request.call_args == mock.call(
                False,
                cluster_identify.commands_by_name["trigger_effect"].id,
                cluster_identify.commands_by_name["trigger_effect"].schema,
                effect_id=zigpy.zcl.clusters.general.Identify.EffectIdentifier.Okay,
                effect_variant=(
                    zigpy.zcl.clusters.general.Identify.EffectVariant.Default
                ),
                expect_reply=True,
                manufacturer=None,
                tries=1,
                tsn=None,
            )

    event_channels = {
        ch.id for pool in zha_dev.channels.pools for ch in pool.client_channels.values()
    }
    assert event_channels == set(device[DEV_SIG_EVT_CHANNELS])
    # we need to probe the class create entity factory so we need to reset this to get accurate results
    zha_regs.ZHA_ENTITIES.clean_up()
    # build a dict of entity_class -> (component, unique_id, channels) tuple
    ha_ent_info = {}
    created_entity_count = 0
    for call in _dispatch.call_args_list:
        _, component, entity_cls, unique_id, channels = call[0]
        # the factory can return None. We filter these out to get an accurate created entity count
        response = entity_cls.create_entity(unique_id, zha_dev, channels)
        if response and not contains_ignored_suffix(response.name):
            created_entity_count += 1
            unique_id_head = UNIQUE_ID_HD.match(unique_id).group(
                0
            )  # ieee + endpoint_id
            ha_ent_info[(unique_id_head, entity_cls.__name__)] = (
                component,
                unique_id,
                channels,
            )

    for comp_id, ent_info in device[DEV_SIG_ENT_MAP].items():
        component, unique_id = comp_id
        no_tail_id = NO_TAIL_ID.sub("", ent_info[DEV_SIG_ENT_MAP_ID])
        ha_entity_id = entity_registry.async_get_entity_id(component, "zha", unique_id)
        assert ha_entity_id is not None
        assert ha_entity_id.startswith(no_tail_id)

        test_ent_class = ent_info[DEV_SIG_ENT_MAP_CLASS]
        test_unique_id_head = UNIQUE_ID_HD.match(unique_id).group(0)
        assert (test_unique_id_head, test_ent_class) in ha_ent_info

        ha_comp, ha_unique_id, ha_channels = ha_ent_info[
            (test_unique_id_head, test_ent_class)
        ]
        assert component is ha_comp.value
        # unique_id used for discover is the same for "multi entities"
        assert unique_id.startswith(ha_unique_id)
        assert {ch.name for ch in ha_channels} == set(ent_info[DEV_SIG_CHANNELS])

    assert created_entity_count == len(device[DEV_SIG_ENT_MAP])

    entity_ids = hass_disable_services.states.async_entity_ids()
    await hass_disable_services.async_block_till_done()

    zha_entity_ids = {
        ent
        for ent in entity_ids
        if not contains_ignored_suffix(ent) and ent.split(".")[0] in zha_const.PLATFORMS
    }
    assert zha_entity_ids == {
        e[DEV_SIG_ENT_MAP_ID] for e in device[DEV_SIG_ENT_MAP].values()
    }


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
def test_discover_entities(m1, m2) -> None:
    """Test discover endpoint class method."""
    ep_channels = mock.MagicMock()
    disc.PROBE.discover_entities(ep_channels)
    assert m1.call_count == 1
    assert m1.call_args[0][0] is ep_channels
    assert m2.call_count == 1
    assert m2.call_args[0][0] is ep_channels


@pytest.mark.parametrize(
    ("device_type", "component", "hit"),
    [
        (zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT, Platform.LIGHT, True),
        (zigpy.profiles.zha.DeviceType.ON_OFF_BALLAST, Platform.SWITCH, True),
        (zigpy.profiles.zha.DeviceType.SMART_PLUG, Platform.SWITCH, True),
        (0xFFFF, None, False),
    ],
)
def test_discover_by_device_type(device_type, component, hit) -> None:
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


def test_discover_by_device_type_override() -> None:
    """Test entity discovery by device type overriding."""

    ep_channels = mock.MagicMock(spec_set=zha_channels.ChannelPool)
    ep_mock = mock.PropertyMock()
    ep_mock.return_value.profile_id = 0x0104
    ep_mock.return_value.device_type = 0x0100
    type(ep_channels).endpoint = ep_mock

    overrides = {ep_channels.unique_id: {"type": Platform.SWITCH}}
    get_entity_mock = mock.MagicMock(
        return_value=(mock.sentinel.entity_cls, mock.sentinel.claimed)
    )
    with mock.patch(
        "homeassistant.components.zha.core.registries.ZHA_ENTITIES.get_entity",
        get_entity_mock,
    ), mock.patch.dict(disc.PROBE._device_configs, overrides, clear=True):
        disc.PROBE.discover_by_device_type(ep_channels)
        assert get_entity_mock.call_count == 1
        assert ep_channels.claim_channels.call_count == 1
        assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
        assert ep_channels.async_new_entity.call_count == 1
        assert ep_channels.async_new_entity.call_args[0][0] == Platform.SWITCH
        assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity_cls


def test_discover_probe_single_cluster() -> None:
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
        disc.PROBE.probe_single_cluster(Platform.SWITCH, channel_mock, ep_channels)

    assert get_entity_mock.call_count == 1
    assert ep_channels.claim_channels.call_count == 1
    assert ep_channels.claim_channels.call_args[0][0] is mock.sentinel.claimed
    assert ep_channels.async_new_entity.call_count == 1
    assert ep_channels.async_new_entity.call_args[0][0] == Platform.SWITCH
    assert ep_channels.async_new_entity.call_args[0][1] == mock.sentinel.entity_cls
    assert ep_channels.async_new_entity.call_args[0][3] == mock.sentinel.claimed


@pytest.mark.parametrize("device_info", DEVICES)
async def test_discover_endpoint(
    device_info, channels_mock, hass: HomeAssistant
) -> None:
    """Test device discovery."""

    with mock.patch(
        "homeassistant.components.zha.core.channels.Channels.async_new_entity"
    ) as new_ent:
        channels = channels_mock(
            device_info[SIG_ENDPOINTS],
            manufacturer=device_info[SIG_MANUFACTURER],
            model=device_info[SIG_MODEL],
            node_desc=device_info[SIG_NODE_DESC],
            patch_cluster=False,
        )

    assert device_info[DEV_SIG_EVT_CHANNELS] == sorted(
        ch.id for pool in channels.pools for ch in pool.client_channels.values()
    )

    # build a dict of entity_class -> (component, unique_id, channels) tuple
    ha_ent_info = {}
    for call in new_ent.call_args_list:
        component, entity_cls, unique_id, channels = call[0]
        if not contains_ignored_suffix(unique_id):
            unique_id_head = UNIQUE_ID_HD.match(unique_id).group(
                0
            )  # ieee + endpoint_id
            ha_ent_info[(unique_id_head, entity_cls.__name__)] = (
                component,
                unique_id,
                channels,
            )

    for comp_id, ent_info in device_info[DEV_SIG_ENT_MAP].items():
        component, unique_id = comp_id

        test_ent_class = ent_info[DEV_SIG_ENT_MAP_CLASS]
        test_unique_id_head = UNIQUE_ID_HD.match(unique_id).group(0)
        assert (test_unique_id_head, test_ent_class) in ha_ent_info

        ha_comp, ha_unique_id, ha_channels = ha_ent_info[
            (test_unique_id_head, test_ent_class)
        ]
        assert component is ha_comp.value
        # unique_id used for discover is the same for "multi entities"
        assert unique_id.startswith(ha_unique_id)
        assert {ch.name for ch in ha_channels} == set(ent_info[DEV_SIG_CHANNELS])


def _ch_mock(cluster):
    """Return mock of a channel with a cluster."""
    channel = mock.MagicMock()
    type(channel).cluster = mock.PropertyMock(return_value=cluster(mock.MagicMock()))
    return channel


@mock.patch(
    (
        "homeassistant.components.zha.core.discovery.ProbeEndpoint"
        ".handle_on_off_output_cluster_exception"
    ),
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
    ]

    disc.ProbeEndpoint().discover_by_cluster_id(ch_pool)
    assert probe_mock.call_count == len(ch_pool.unclaimed_channels())
    probes = (
        (Platform.LOCK, door_ch),
        (Platform.COVER, cover_ch),
        (Platform.SENSOR, multistate_ch),
        (Platform.BINARY_SENSOR, ias_ch),
        (Platform.SENSOR, analog_ch),
    )
    for call, details in zip(probe_mock.call_args_list, probes):
        component, ch = details
        assert call[0][0] == component
        assert call[0][1] == ch


def test_single_input_cluster_device_class_by_cluster_class() -> None:
    """Test SINGLE_INPUT_CLUSTER_DEVICE_CLASS matching by cluster id or class."""
    mock_reg = {
        zigpy.zcl.clusters.closures.DoorLock.cluster_id: Platform.LOCK,
        zigpy.zcl.clusters.closures.WindowCovering.cluster_id: Platform.COVER,
        zigpy.zcl.clusters.general.AnalogInput: Platform.SENSOR,
        zigpy.zcl.clusters.general.MultistateInput: Platform.SENSOR,
        zigpy.zcl.clusters.security.IasZone: Platform.BINARY_SENSOR,
    }

    with mock.patch.dict(
        zha_regs.SINGLE_INPUT_CLUSTER_DEVICE_CLASS, mock_reg, clear=True
    ):
        _test_single_input_cluster_device_class()


@pytest.mark.parametrize(
    ("override", "entity_id"),
    [
        (None, "light.manufacturer_model_light"),
        ("switch", "switch.manufacturer_model_switch"),
    ],
)
async def test_device_override(
    hass_disable_services, zigpy_device_mock, setup_zha, override, entity_id
) -> None:
    """Test device discovery override."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                "endpoint_id": 1,
                SIG_EP_INPUT: [0, 3, 4, 5, 6, 8, 768, 2821, 64513],
                SIG_EP_OUTPUT: [25],
                SIG_EP_PROFILE: 260,
            }
        },
        "00:11:22:33:44:55:66:77",
        "manufacturer",
        "model",
        patch_cluster=False,
    )

    if override is not None:
        override = {"device_config": {"00:11:22:33:44:55:66:77-1": {"type": override}}}

    await setup_zha(override)
    assert hass_disable_services.states.get(entity_id) is None
    zha_gateway = get_zha_gateway(hass_disable_services)
    await zha_gateway.async_device_initialized(zigpy_device)
    await hass_disable_services.async_block_till_done()
    assert hass_disable_services.states.get(entity_id) is not None


async def test_group_probe_cleanup_called(
    hass_disable_services, setup_zha, config_entry
) -> None:
    """Test cleanup happens when ZHA is unloaded."""
    await setup_zha()
    disc.GROUP_PROBE.cleanup = mock.Mock(wraps=disc.GROUP_PROBE.cleanup)
    await config_entry.async_unload(hass_disable_services)
    await hass_disable_services.async_block_till_done()
    disc.GROUP_PROBE.cleanup.assert_called()


@patch(
    "zigpy.zcl.clusters.general.Identify.request",
    new=AsyncMock(return_value=[mock.sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "homeassistant.components.zha.entity.ZhaEntity.entity_registry_enabled_default",
    new=Mock(return_value=True),
)
async def test_channel_with_empty_ep_attribute_cluster(
    hass_disable_services,
    zigpy_device_mock,
    zha_device_joined_restored,
) -> None:
    """Test device discovery for cluster which does not have em_attribute."""
    entity_registry = homeassistant.helpers.entity_registry.async_get(
        hass_disable_services
    )

    zigpy_device = zigpy_device_mock(
        {1: {SIG_EP_INPUT: [0x042E], SIG_EP_OUTPUT: [], SIG_EP_TYPE: 0x1234}},
        "00:11:22:33:44:55:66:77",
        "test manufacturer",
        "test model",
        patch_cluster=False,
    )
    zha_dev = await zha_device_joined_restored(zigpy_device)
    ha_entity_id = entity_registry.async_get_entity_id(
        "sensor", "zha", f"{zha_dev.ieee}-1-1070"
    )
    assert ha_entity_id is not None
