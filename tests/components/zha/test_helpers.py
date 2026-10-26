"""Tests for ZHA helpers."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from probatio import to_field_list
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from zha.application.const import ATTR_TYPE, ZHA_GW_MSG
from zigpy.application import ControllerApplication
import zigpy.device
from zigpy.profiles import zha
from zigpy.types.basic import uint16_t
from zigpy.zcl.clusters import general, lighting

from homeassistant.components.zha import const as zha_const
from homeassistant.components.zha.helpers import (
    ZHA_GW_MSG_LOG_ENTRY,
    ZHA_GW_MSG_LOG_OUTPUT,
    ZHAGroupProxy,
    _group_id_from_device_identifier,
    cluster_command_schema_to_vol_schema,
    convert_to_zcl_values,
    create_zha_config,
    exclude_none_values,
    get_zha_data,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    FIXTURE_GRP_ID,
    FIXTURE_GRP_NAME,
    FIXTURE_GRP_WITH_ENTITIES_ID,
    FIXTURE_GRP_WITH_ENTITIES_NAME,
    SIG_EP_INPUT,
    SIG_EP_OUTPUT,
    SIG_EP_PROFILE,
    SIG_EP_TYPE,
)

_LOGGER = logging.getLogger(__name__)


async def test_zcl_schema_conversions(hass: HomeAssistant) -> None:
    """Test ZHA ZCL schema conversion helpers."""
    command_schema = lighting.Color.ServerCommandDefs.color_loop_set.schema
    expected_schema = [
        {
            "type": "multi_select",
            "options": ["Action", "Direction", "Time", "Start Hue"],
            "name": "update_flags",
            "required": True,
        },
        {
            "type": "select",
            "options": [
                ("Deactivate", "Deactivate"),
                ("Activate from color loop hue", "Activate from color loop hue"),
                ("Activate from current hue", "Activate from current hue"),
            ],
            "name": "action",
            "required": True,
        },
        {
            "type": "select",
            "options": [("Decrement", "Decrement"), ("Increment", "Increment")],
            "name": "direction",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 65535,
            "name": "time",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 65535,
            "name": "start_hue",
            "required": True,
        },
        {
            "type": "multi_select",
            "options": ["Execute if off present"],
            "name": "options_mask",
            "optional": True,
            "required": False,
        },
        {
            "type": "multi_select",
            "options": ["Execute if off"],
            "name": "options_override",
            "optional": True,
            "required": False,
        },
    ]
    vol_schema = to_field_list(
        cluster_command_schema_to_vol_schema(command_schema),
        custom_serializer=cv.custom_serializer,
    )
    assert vol_schema == expected_schema

    raw_data = {
        "update_flags": ["Action", "Start Hue"],
        "action": "Activate from current hue",
        "direction": "Increment",
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    assert isinstance(
        converted_data["update_flags"], lighting.Color.ColorLoopUpdateFlags
    )
    assert lighting.Color.ColorLoopUpdateFlags.Action in converted_data["update_flags"]
    assert (
        lighting.Color.ColorLoopUpdateFlags.Start_Hue in converted_data["update_flags"]
    )

    assert isinstance(converted_data["action"], lighting.Color.ColorLoopAction)
    assert (
        converted_data["action"]
        == lighting.Color.ColorLoopAction.Activate_from_current_hue
    )

    assert isinstance(converted_data["direction"], lighting.Color.ColorLoopDirection)
    assert converted_data["direction"] == lighting.Color.ColorLoopDirection.Increment

    assert isinstance(converted_data["time"], uint16_t)
    assert converted_data["time"] == 20

    assert isinstance(converted_data["start_hue"], uint16_t)
    assert converted_data["start_hue"] == 196

    raw_data = {
        "update_flags": [0b0000_0001, 0b0000_1000],
        "action": 0x02,
        "direction": 0x01,
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    assert isinstance(
        converted_data["update_flags"], lighting.Color.ColorLoopUpdateFlags
    )
    assert lighting.Color.ColorLoopUpdateFlags.Action in converted_data["update_flags"]
    assert (
        lighting.Color.ColorLoopUpdateFlags.Start_Hue in converted_data["update_flags"]
    )

    assert isinstance(converted_data["action"], lighting.Color.ColorLoopAction)
    assert (
        converted_data["action"]
        == lighting.Color.ColorLoopAction.Activate_from_current_hue
    )

    assert isinstance(converted_data["direction"], lighting.Color.ColorLoopDirection)
    assert converted_data["direction"] == lighting.Color.ColorLoopDirection.Increment

    assert isinstance(converted_data["time"], uint16_t)
    assert converted_data["time"] == 20

    assert isinstance(converted_data["start_hue"], uint16_t)
    assert converted_data["start_hue"] == 196

    # This time, the update flags bitmap is empty
    raw_data = {
        "update_flags": [],
        "action": 0x02,
        "direction": 0x01,
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    # No flags are passed through
    assert converted_data["update_flags"] == 0


@pytest.mark.parametrize(
    ("obj", "expected_output"),
    [
        ({"a": 1, "b": 2, "c": None}, {"a": 1, "b": 2}),
        ({"a": 1, "b": 2, "c": 0}, {"a": 1, "b": 2, "c": 0}),
        ({"a": 1, "b": 2, "c": ""}, {"a": 1, "b": 2, "c": ""}),
        ({"a": 1, "b": 2, "c": False}, {"a": 1, "b": 2, "c": False}),
    ],
)
def test_exclude_none_values(
    obj: dict[str, Any], expected_output: dict[str, Any]
) -> None:
    """Test exclude_none_values helper."""
    result = exclude_none_values(obj)
    assert result == expected_output

    for key, value in expected_output.items():
        assert value == obj[key]


async def test_create_zha_config_remove_unused(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect: ControllerApplication,
) -> None:
    """Test creating ZHA config data with unused keys."""
    config_entry.add_to_hass(hass)

    options = config_entry.options.copy()
    options["custom_configuration"]["zha_options"]["some_random_key"] = "a value"

    hass.config_entries.async_update_entry(config_entry, options=options)

    assert (
        config_entry.options["custom_configuration"]["zha_options"]["some_random_key"]
        == "a value"
    )

    status = await async_setup_component(
        hass,
        zha_const.DOMAIN,
        {zha_const.DOMAIN: {zha_const.CONF_ENABLE_QUIRKS: False}},
    )
    assert status is True
    await hass.async_block_till_done()

    ha_zha_data = get_zha_data(hass)

    # Does not error out
    create_zha_config(hass, ha_zha_data)


async def test_debug_mode_log_filter(
    hass: HomeAssistant, setup_zha: Callable[..., Coroutine[None]]
) -> None:
    """Test a debug mode session filters relayed logs only until it ends."""
    await setup_zha()
    gateway_proxy = get_zha_gateway_proxy(hass)

    relayed: list[str] = []
    marker_relayed = asyncio.Event()

    @callback
    def collect(data: dict[str, Any]) -> None:
        if data[ATTR_TYPE] != ZHA_GW_MSG_LOG_OUTPUT:
            return
        message = data[ZHA_GW_MSG_LOG_ENTRY]["message"][0]
        if message.startswith("test "):
            relayed.append(message)
        if message == "test marker":
            marker_relayed.set()

    unsub = async_dispatcher_connect(hass, ZHA_GW_MSG, collect)

    async def log_and_wait(*messages: str) -> None:
        # The relay is a queue, so the marker arrives after everything before it
        marker_relayed.clear()
        for message in (*messages, "test marker"):
            logging.getLogger("zha").debug(message)
        async with asyncio.timeout(5):
            await marker_relayed.wait()

    def drop_filtered(record: logging.LogRecord) -> bool:
        return record.getMessage() != "test filtered"

    gateway_proxy.async_enable_debug_mode(drop_filtered)
    await log_and_wait("test filtered", "test kept")
    gateway_proxy.async_disable_debug_mode(drop_filtered)
    assert relayed == ["test kept", "test marker"]

    # A later session without the filter relays everything again
    relayed.clear()
    gateway_proxy.async_enable_debug_mode()
    await log_and_wait("test filtered")
    gateway_proxy.async_disable_debug_mode()
    assert relayed == ["test filtered", "test marker"]

    # Ending the filtered session removes its filter while another one is open
    relayed.clear()
    gateway_proxy.async_enable_debug_mode(drop_filtered)
    gateway_proxy.async_enable_debug_mode()
    gateway_proxy.async_disable_debug_mode(drop_filtered)
    await log_and_wait("test filtered")
    gateway_proxy.async_disable_debug_mode()
    assert relayed == ["test filtered", "test marker"]

    unsub()
@pytest.mark.parametrize(
    ("group_id", "expected_identifier"),
    [
        (0x0001, "test_entry_id_group_0x0001"),
        (0x1001, "test_entry_id_group_0x1001"),
        (0xFFFF, "test_entry_id_group_0xffff"),
    ],
)
def test_zha_group_proxy_device_identifier(
    group_id: int, expected_identifier: str
) -> None:
    """Test ZHAGroupProxy device_identifier property."""
    gateway_proxy = MagicMock()
    gateway_proxy.config_entry.entry_id = "test_entry_id"
    group_proxy = ZHAGroupProxy(MagicMock(group_id=group_id), gateway_proxy)
    assert group_proxy.device_identifier == expected_identifier


@pytest.mark.parametrize(
    ("identifier", "expected_group_id"),
    [
        ("test_entry_id_group_0x0001", 0x0001),
        ("test_entry_id_group_0x1001", 0x1001),
        # the legacy group entity unique id form is not a device identifier
        ("zha_group_0x1001", None),
        # another config entry's group device
        ("other_entry_id_group_0x1001", None),
        ("00:15:8d:00:02:32:4f:32", None),
        ("test_entry_id_group_0xnothex", None),
        ("test_entry_id_group_0x1", None),
        ("test_entry_id_group_0x 123", None),
    ],
)
def test_group_id_from_device_identifier(
    identifier: str, expected_group_id: int | None
) -> None:
    """Test parsing the group id from a group device identifier."""
    assert (
        _group_id_from_device_identifier("test_entry_id", identifier)
        == expected_group_id
    )


def test_zha_group_proxy_device_info() -> None:
    """Test ZHAGroupProxy device_info returns correct DeviceInfo."""
    mock_group = MagicMock(group_id=0x1001)
    mock_group.name = "Test Group"
    coordinator_ieee = "00:15:8d:00:02:32:4f:32"
    gateway_proxy = MagicMock()
    gateway_proxy.config_entry.entry_id = "test_entry_id"
    gateway_proxy.gateway.state.node_info.ieee = coordinator_ieee

    with patch(
        "homeassistant.components.zha.helpers.dr.async_get_device_id_by_identifier",
        return_value="coordinator_device_id",
    ) as mock_get_device_id:
        device_info = ZHAGroupProxy(mock_group, gateway_proxy).device_info

    assert device_info == dr.DeviceInfo(
        identifiers={(zha_const.DOMAIN, "test_entry_id_group_0x1001")},
        name="Test Group",
        manufacturer="Zigbee",
        model="Group",
        entry_type=dr.DeviceEntryType.SERVICE,
        via_device_id="coordinator_device_id",
    )
    assert mock_get_device_id.mock_calls[0].args[1] == (
        zha_const.DOMAIN,
        coordinator_ieee,
    )


async def test_zha_group_proxy_device_id_property(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test ZHAGroupProxy device_id property getter, setter and registry lookup."""
    config_entry = MockConfigEntry(domain=zha_const.DOMAIN)
    config_entry.add_to_hass(hass)
    gateway_proxy = MagicMock(hass=hass)
    gateway_proxy.config_entry.entry_id = config_entry.entry_id
    group_proxy = ZHAGroupProxy(MagicMock(group_id=0x1001), gateway_proxy)

    assert group_proxy.device_id is None
    group_proxy.device_id = "test_device_id"
    assert group_proxy.device_id == "test_device_id"

    # The device id is resolved from the device registry when not cached
    group_proxy = ZHAGroupProxy(MagicMock(group_id=0x1001), gateway_proxy)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(zha_const.DOMAIN, group_proxy.device_identifier)},
    )
    assert group_proxy.device_id == device.id


async def test_zha_group_proxy_no_device_for_group_without_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
) -> None:
    """Test that no device is created for groups without entities."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)

    group_proxy = gateway_proxy.group_proxies.get(FIXTURE_GRP_ID)
    assert group_proxy is not None
    assert group_proxy.group.name == FIXTURE_GRP_NAME
    # Fixture group has no members, so no entities, so no device
    assert not group_proxy.group.group_entities
    assert group_proxy.device_id is None


async def test_zha_group_device_creation_with_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a device is created for groups with entities."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]

    assert group_proxy.group.group_entities
    assert group_proxy.device_id is not None

    device = device_registry.async_get(group_proxy.device_id)
    assert device is not None
    assert device.name == FIXTURE_GRP_WITH_ENTITIES_NAME
    assert device.manufacturer == "Zigbee"
    assert device.model == "Group"
    assert device.entry_type == dr.DeviceEntryType.SERVICE

    # Verify via_device points to coordinator
    gateway = get_zha_gateway(hass)
    coordinator_ieee = str(gateway.state.node_info.ieee)
    coordinator_device = device_registry.async_get_device_by_identifier(
        ("zha", coordinator_ieee), gateway_proxy.config_entry.entry_id
    )
    assert coordinator_device is not None
    assert device.via_device_id == coordinator_device.id


async def test_zha_group_cleanup_on_removal(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that device and entities are cleaned up when a group is removed."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    device_id = group_proxy.device_id
    assert device_id is not None

    # Collect entity entries for the group device before removal
    entity_entries = er.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    assert len(entity_entries) > 0
    entity_keys = [
        (entry.domain, entry.platform, entry.unique_id) for entry in entity_entries
    ]

    # Remove the group
    await gateway.async_remove_zigpy_group(FIXTURE_GRP_WITH_ENTITIES_ID)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Device should be removed from device registry
    assert device_registry.async_get(device_id) is None
    # ... and the proxy's cached device id is dropped with it
    assert group_proxy.device_id is None

    # Entities should be removed from the entity registry
    for domain, platform, unique_id in entity_keys:
        assert entity_registry.async_get_entity_id(domain, platform, unique_id) is None


async def test_zha_group_device_created_when_entities_appear(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_switches: ControllerApplication,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the device is created once a group gains enough members."""
    await setup_zha()

    app_controller = zigpy_app_controller_with_switches
    gateway_proxy = get_zha_gateway_proxy(hass)

    group = app_controller.groups.add_group(
        FIXTURE_GRP_WITH_ENTITIES_ID, FIXTURE_GRP_WITH_ENTITIES_NAME
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert not group_proxy.group.group_entities
    assert group_proxy.device_id is None

    coordinator_ieee = app_controller.state.node_info.ieee
    device_1, device_2 = (
        device
        for device in app_controller.devices.values()
        if device.ieee != coordinator_ieee
    )
    group.add_member(device_1.endpoints[1])
    await hass.async_block_till_done(wait_background_tasks=True)

    # A single member is not enough for group entities, so still no device
    assert not group_proxy.group.group_entities
    assert group_proxy.device_id is None

    group.add_member(device_2.endpoints[1])
    await hass.async_block_till_done(wait_background_tasks=True)

    assert group_proxy.group.group_entities
    assert group_proxy.device_id is not None
    assert device_registry.async_get(group_proxy.device_id) is not None


async def test_zha_group_cleanup_legacy_coordinator_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that legacy group entities tied to the coordinator are cleaned up."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    gateway_proxy = get_zha_gateway_proxy(hass)

    coordinator_device = device_registry.async_get_device_by_identifier(
        (zha_const.DOMAIN, str(gateway.state.node_info.ieee)),
        gateway_proxy.config_entry.entry_id,
    )
    assert coordinator_device is not None

    # Simulate a stale group entity entry created by an older HA Core version,
    # tied to the coordinator device
    legacy_unique_id = f"switch_zha_group_0x{FIXTURE_GRP_ID:04x}"
    legacy_entry = entity_registry.async_get_or_create(
        "switch",
        zha_const.DOMAIN,
        legacy_unique_id,
        config_entry=gateway_proxy.config_entry,
        device_id=coordinator_device.id,
    )
    await hass.async_block_till_done()

    # The memberless fixture group has no entities and thus no group device
    assert gateway_proxy.group_proxies[FIXTURE_GRP_ID].device_id is None

    await gateway.async_remove_zigpy_group(FIXTURE_GRP_ID)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(legacy_entry.entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            "switch", zha_const.DOMAIN, legacy_unique_id
        )
        is None
    )


async def test_zha_group_device_kept_when_group_shrinks(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a shrinking group loses its entities but keeps its device."""
    await setup_zha()

    app_controller = zigpy_app_controller_with_group
    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]

    device_id = group_proxy.device_id
    assert device_id is not None
    entity_entries = er.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    assert len(entity_entries) > 0

    # drop the group below two members, so it no longer has group entities
    group = app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    member = next(iter(group.values()))
    group.remove_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not group_proxy.group.group_entities
    for entry in entity_entries:
        assert entity_registry.async_get(entry.entity_id) is None
    # the group itself still exists, so its device stays
    assert device_registry.async_get(device_id) is not None
    assert group_proxy.device_id == device_id

    group.add_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert group_proxy.group.group_entities
    assert group_proxy.device_id == device_id
    assert er.async_entries_for_device(entity_registry, device_id)


async def test_zha_group_device_id_reuse_starts_clean(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test a new group reusing a removed group's id starts with a clean device."""
    await setup_zha()

    app_controller = zigpy_app_controller_with_group
    gateway = get_zha_gateway(hass)
    gateway_proxy = get_zha_gateway_proxy(hass)
    device_id = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID].device_id
    assert device_id is not None
    device_registry.async_update_device(
        device_id,
        area_id=area_registry.async_create("Kitchen").id,
        disabled_by=dr.DeviceEntryDisabler.USER,
        labels={label_registry.async_create("Lights").label_id},
        name_by_user="Old group",
    )
    members = list(app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID].values())

    await gateway.async_remove_zigpy_group(FIXTURE_GRP_WITH_ENTITIES_ID)
    await hass.async_block_till_done(wait_background_tasks=True)

    # ZHA hands out the freed group id to the next new group
    group = app_controller.groups.add_group(FIXTURE_GRP_WITH_ENTITIES_ID, "New group")
    for member in members:
        group.add_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    new_device_id = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID].device_id
    assert new_device_id is not None
    device = device_registry.async_get(new_device_id)
    assert device is not None
    assert device.name == "New group"
    assert device.name_by_user is None
    assert device.area_id is None
    assert device.labels == set()
    assert device.disabled_by is None


def _remove_group_while_stopped(app_controller: ControllerApplication) -> None:
    """Remove the group without emitting the zigpy group events."""
    dict.pop(app_controller.groups, FIXTURE_GRP_WITH_ENTITIES_ID)


def _shrink_group_while_stopped(app_controller: ControllerApplication) -> None:
    """Drop the group below two members without emitting zigpy group events."""
    group = app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    group.remove_member(next(iter(group.values())), suppress_event=True)


@pytest.mark.parametrize(
    ("change_group", "removed"),
    [
        pytest.param(_remove_group_while_stopped, True, id="group_removed"),
        # entries disabled by the device are kept until the device is enabled
        pytest.param(_shrink_group_while_stopped, False, id="group_shrunk"),
    ],
)
async def test_zha_group_device_reconciled_on_startup(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    change_group: Callable[[ControllerApplication], None],
    removed: bool,
) -> None:
    """Test group changes made while ZHA was not running are cleaned up on setup."""
    await setup_zha()

    device_id = (
        get_zha_gateway_proxy(hass)
        .group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
        .device_id
    )
    assert device_id is not None
    # a disabled group device disables its entities, too
    device_registry.async_update_device(
        device_id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    entity_entries = er.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    assert entity_entries

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    change_group(zigpy_app_controller_with_group)
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
        await hass.async_block_till_done(wait_background_tasks=True)

    # resetting the removed device must not re-enable entities and reload ZHA
    mock_reload.assert_not_called()
    assert (device_registry.async_get(device_id) is None) is removed
    for entry in entity_entries:
        assert (entity_registry.async_get(entry.entity_id) is None) is removed


async def test_zha_group_stale_entity_removed_on_startup(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group entity the group no longer has is removed on setup."""
    await setup_zha()

    group_proxy = get_zha_gateway_proxy(hass).group_proxies[
        FIXTURE_GRP_WITH_ENTITIES_ID
    ]
    device_id = group_proxy.device_id
    assert device_id is not None
    current_entries = er.async_entries_for_device(entity_registry, device_id)
    assert current_entries

    # e.g. left behind by a ZHA version that created other group entities
    stale_entry = entity_registry.async_get_or_create(
        "light",
        zha_const.DOMAIN,
        f"light_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
        config_entry=config_entry,
        device_id=device_id,
    )
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(stale_entry.entity_id) is None
    assert device_registry.async_get(device_id) is not None
    for entry in current_entries:
        assert entity_registry.async_get(entry.entity_id) is not None


async def test_zha_group_entity_registry_disable_propagates(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling a group entity in the registry disables the ZHA entity."""
    await setup_zha()

    group_proxy = get_zha_gateway_proxy(hass).group_proxies[
        FIXTURE_GRP_WITH_ENTITIES_ID
    ]
    assert group_proxy.device_id is not None
    [entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity = group_proxy.group.group_entities[entry.unique_id]
    assert group_entity.enabled

    entity_registry.async_update_entity(
        entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert not group_entity.enabled

    entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert group_entity.enabled


async def test_zha_group_entity_enabled_after_regrow_of_disabled_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group entity is enabled again after its device was disabled.

    The group shrinks while its device is disabled and grows back after the
    device was enabled again.
    """
    await setup_zha()

    group_proxy = get_zha_gateway_proxy(hass).group_proxies[
        FIXTURE_GRP_WITH_ENTITIES_ID
    ]
    device_id = group_proxy.device_id
    assert device_id is not None
    [entry] = er.async_entries_for_device(entity_registry, device_id)

    device_registry.async_update_device(
        device_id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()

    group = zigpy_app_controller_with_group.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    member = next(iter(group.values()))
    group.remove_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_registry.async_update_device(device_id, disabled_by=None)
    await hass.async_block_till_done()

    group.add_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    regrown_entry = entity_registry.async_get(entry.entity_id)
    assert regrown_entry is not None
    assert regrown_entry.disabled_by is None
    assert hass.states.get(entry.entity_id) is not None


async def test_zha_group_entity_migrated_from_coordinator_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an existing group entity moves from the coordinator to the group device.

    Before group devices existed, group entities were registered against the
    coordinator device. Upgrading must keep the entity id and move the entry,
    not orphan it or create a duplicate.
    """
    config_entry.add_to_hass(hass)
    coordinator_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (
                zha_const.DOMAIN,
                str(zigpy_app_controller_with_group.state.node_info.ieee),
            )
        },
    )
    legacy_unique_id = f"switch_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}"
    legacy_entry = entity_registry.async_get_or_create(
        "switch",
        zha_const.DOMAIN,
        legacy_unique_id,
        config_entry=config_entry,
        device_id=coordinator_device.id,
        original_name="Test Group",
        # the entity id an upgrading user actually has: derived from the
        # coordinator device name, not from the group name
        suggested_object_id="coordinator_manufacturer_coordinator_model_test_group",
    )
    assert legacy_entry.device_id == coordinator_device.id
    assert legacy_entry.entity_id == (
        "switch.coordinator_manufacturer_coordinator_model_test_group"
    )
    # user customisation that must survive the move
    entity_registry.async_update_entity(
        legacy_entry.entity_id, name="My kitchen group", icon="mdi:test"
    )

    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    migrated_entry = entity_registry.async_get(legacy_entry.entity_id)
    assert migrated_entry is not None
    # same entity id, now pointing at the group device
    assert migrated_entry.entity_id == legacy_entry.entity_id
    assert migrated_entry.device_id == group_proxy.device_id
    # and the user's customisation is untouched
    assert migrated_entry.name == "My kitchen group"
    assert migrated_entry.icon == "mdi:test"
    # and no duplicate was created for the same unique id
    assert (
        entity_registry.async_get_entity_id(
            "switch", zha_const.DOMAIN, legacy_unique_id
        )
        == legacy_entry.entity_id
    )
    # no group entity is left behind on the coordinator device
    assert not [
        entry
        for entry in er.async_entries_for_device(
            entity_registry, coordinator_device.id, include_disabled_entities=True
        )
        if "_zha_group_0x" in entry.unique_id
    ]


@pytest.mark.parametrize(
    ("domain", "legacy_unique_id"),
    [
        pytest.param(
            "switch", f"switch_zha_group_0x{FIXTURE_GRP_ID:04x}", id="no_entities"
        ),
        pytest.param("light", "light_zha_group_0x3001", id="group_gone"),
    ],
)
async def test_zha_group_stale_legacy_entity_removed_on_startup(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    domain: str,
    legacy_unique_id: str,
) -> None:
    """Test legacy coordinator group entities that no longer exist are removed."""
    config_entry.add_to_hass(hass)
    coordinator_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (
                zha_const.DOMAIN,
                str(zigpy_app_controller_with_group.state.node_info.ieee),
            )
        },
    )
    stale_entry = entity_registry.async_get_or_create(
        domain,
        zha_const.DOMAIN,
        legacy_unique_id,
        config_entry=config_entry,
        device_id=coordinator_device.id,
    )
    # not a group entity, so it is left alone
    other_entry = entity_registry.async_get_or_create(
        "sensor",
        zha_const.DOMAIN,
        "sensor_zha_group_0xgggg",
        config_entry=config_entry,
        device_id=coordinator_device.id,
    )

    await setup_zha()

    assert entity_registry.async_get(stale_entry.entity_id) is None
    assert entity_registry.async_get(other_entry.entity_id) is not None


async def test_zha_group_proxy_associated_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group's entities are reported for each of its members."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    group_entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_device(
            entity_registry, group_proxy.device_id, include_disabled_entities=True
        )
    ]
    assert group_entity_ids

    members = group_proxy.group_info["members"]
    assert len(members) == 2
    for member in members:
        assert [entity["entity_id"] for entity in member["entities"]] == (
            group_entity_ids
        )


async def test_zha_group_entity_reference_follows_entity_id_change(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a renamed group entity is still reported for the group members."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    new_entity_id = f"{entry.domain}.renamed_group"
    entity_registry.async_update_entity(entry.entity_id, new_entity_id=new_entity_id)
    await hass.async_block_till_done()

    assert gateway_proxy.get_entity_reference(entry.entity_id) is None
    assert gateway_proxy.get_entity_reference(new_entity_id) is not None
    for member in group_proxy.group_info["members"]:
        assert [entity["entity_id"] for entity in member["entities"]] == [new_entity_id]


async def test_zha_group_cleanup_leaves_other_integrations_alone(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    zigpy_device_mock: Callable[..., zigpy.device.Device],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the group cleanup only removes ZHA's own group entities.

    Helper integrations attach their entity to the device of the entity they
    wrap, so an unscoped cleanup would delete them from the group device.
    """
    await setup_zha()

    app_controller = zigpy_app_controller_with_group
    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    other_config_entry = MockConfigEntry(domain="switch_as_x")
    other_config_entry.add_to_hass(hass)
    foreign_entry = entity_registry.async_get_or_create(
        "light",
        "switch_as_x",
        "some_helper_unique_id",
        config_entry=other_config_entry,
        device_id=group_proxy.device_id,
    )

    # an ordinary action: add a new member to the group
    third_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.OnOff.cluster_id,
                    general.Basic.cluster_id,
                    general.Groups.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e3",
    )
    app_controller.devices[third_device.ieee] = third_device
    group = app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    group.add_member(third_device.endpoints[1])
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(foreign_entry.entity_id) is not None

    # removing the group removes the group device, which detaches the other
    # integration's entity instead of removing it
    await get_zha_gateway(hass).async_remove_zigpy_group(FIXTURE_GRP_WITH_ENTITIES_ID)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert group_proxy.device_id is None
    detached_entry = entity_registry.async_get(foreign_entry.entity_id)
    assert detached_entry is not None
    assert detached_entry.device_id is None
