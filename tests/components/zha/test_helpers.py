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
    issue_registry as ir,
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
        configuration_url=f"homeassistant://config/zha/group/{0x1001}",
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
    assert device.configuration_url == (
        f"homeassistant://config/zha/group/{FIXTURE_GRP_WITH_ENTITIES_ID}"
    )

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


async def test_zha_group_device_removed_when_group_shrinks(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group's device goes with its entities and comes back with them."""
    await setup_zha()

    app_controller = zigpy_app_controller_with_group
    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]

    device_id = group_proxy.device_id
    assert device_id is not None
    area = area_registry.async_create("Kitchen")
    device_registry.async_update_device(device_id, area_id=area.id)
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
    assert device_registry.async_get(device_id) is None
    assert group_proxy.device_id is None

    group.add_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    # the device and its entities are restored, with their settings
    assert group_proxy.device_id == device_id
    device = device_registry.async_get(device_id)
    assert device is not None
    assert device.area_id == area.id
    for entry in entity_entries:
        restored_entry = entity_registry.async_get(entry.entity_id)
        assert restored_entry is not None
        assert restored_entry.device_id == device_id


def _remove_group_while_stopped(app_controller: ControllerApplication) -> None:
    """Remove the group without emitting the zigpy group events."""
    dict.pop(app_controller.groups, FIXTURE_GRP_WITH_ENTITIES_ID)


def _shrink_group_while_stopped(app_controller: ControllerApplication) -> None:
    """Drop the group below two members without emitting zigpy group events."""
    group = app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    group.remove_member(next(iter(group.values())), suppress_event=True)


@pytest.mark.parametrize(
    "change_group",
    [
        pytest.param(_remove_group_while_stopped, id="group_removed"),
        pytest.param(_shrink_group_while_stopped, id="group_shrunk"),
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

    # removing the device must not re-enable entities and reload ZHA
    mock_reload.assert_not_called()
    assert device_registry.async_get(device_id) is None
    for entry in entity_entries:
        assert entity_registry.async_get(entry.entity_id) is None


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


async def test_zha_group_regrown_with_disabled_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group that shrinks and grows back keeps its disabled device."""
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
    assert device_registry.async_get(device_id) is None

    group.add_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get(device_id)
    assert device is not None
    assert device.disabled_by is dr.DeviceEntryDisabler.USER
    regrown_entry = entity_registry.async_get(entry.entity_id)
    assert regrown_entry is not None
    assert regrown_entry.disabled_by is er.RegistryEntryDisabler.DEVICE

    # enabling the device enables its entity again
    device_registry.async_update_device(device_id, disabled_by=None)
    await hass.async_block_till_done()
    regrown_entry = entity_registry.async_get(entry.entity_id)
    assert regrown_entry is not None
    assert regrown_entry.disabled_by is None


def _add_legacy_group_entity(
    app_controller: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    name: str | None,
) -> tuple[dr.DeviceEntry, er.RegistryEntry]:
    """Register a group entity the way older versions did, on the coordinator."""
    coordinator_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(zha_const.DOMAIN, str(app_controller.state.node_info.ieee))},
    )
    legacy_entry = entity_registry.async_get_or_create(
        "switch",
        zha_const.DOMAIN,
        f"switch_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
        config_entry=config_entry,
        device_id=coordinator_device.id,
        original_name="Test Group",
        # the entity id an upgrading user actually has: derived from the
        # coordinator device name, not from the group name
        suggested_object_id="coordinator_manufacturer_coordinator_model_test_group",
    )
    entity_registry.async_update_entity(
        legacy_entry.entity_id, name=name, icon="mdi:test"
    )
    return coordinator_device, legacy_entry


@pytest.mark.parametrize(
    ("custom_name", "device_name_by_user", "friendly_name"),
    [
        pytest.param(
            "My kitchen group", "My kitchen group", "My kitchen group", id="renamed"
        ),
        pytest.param(
            FIXTURE_GRP_WITH_ENTITIES_NAME,
            None,
            FIXTURE_GRP_WITH_ENTITIES_NAME,
            id="named_like_group",
        ),
        pytest.param(None, None, FIXTURE_GRP_WITH_ENTITIES_NAME, id="not_renamed"),
    ],
)
async def test_zha_group_entity_migrated_from_coordinator_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    custom_name: str | None,
    device_name_by_user: str | None,
    friendly_name: str,
) -> None:
    """Test an existing group entity moves from the coordinator to the group device.

    Before group devices existed, group entities were registered against the
    coordinator device. Upgrading must keep the entity id and move the entry,
    not orphan it or create a duplicate, and a custom name the user gave the
    entity becomes the name of the group device.
    """
    config_entry.add_to_hass(hass)
    coordinator_device, legacy_entry = _add_legacy_group_entity(
        zigpy_app_controller_with_group,
        config_entry,
        device_registry,
        entity_registry,
        custom_name,
    )
    assert legacy_entry.entity_id == (
        "switch.coordinator_manufacturer_coordinator_model_test_group"
    )

    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None
    device = device_registry.async_get(group_proxy.device_id)
    assert device is not None
    assert device.name_by_user == device_name_by_user

    migrated_entry = entity_registry.async_get(legacy_entry.entity_id)
    assert migrated_entry is not None
    # same entity id, now pointing at the group device as its main entity
    assert migrated_entry.device_id == group_proxy.device_id
    assert migrated_entry.name is None
    # and the user's other customisations are untouched
    assert migrated_entry.icon == "mdi:test"
    state = hass.states.get(legacy_entry.entity_id)
    assert state is not None
    assert state.name == friendly_name
    # and no duplicate was created for the same unique id
    assert (
        entity_registry.async_get_entity_id(
            "switch", zha_const.DOMAIN, legacy_entry.unique_id
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
    "custom_name", [pytest.param(None, id="no_name"), pytest.param("Lights", id="name")]
)
async def test_zha_group_entity_area_migrated_to_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    custom_name: str | None,
) -> None:
    """Test the area of an existing group entity moves to its group device.

    As the device's main entity, it could not keep an area of its own.
    """
    config_entry.add_to_hass(hass)
    _, legacy_entry = _add_legacy_group_entity(
        zigpy_app_controller_with_group,
        config_entry,
        device_registry,
        entity_registry,
        custom_name,
    )
    area = area_registry.async_create("Kitchen")
    entity_registry.async_update_entity(legacy_entry.entity_id, area_id=area.id)

    await setup_zha()

    entry = entity_registry.async_get(legacy_entry.entity_id)
    assert entry is not None
    assert entry.area_id is None
    assert entry.device_id is not None
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.area_id == area.id
    assert not [
        issue_id
        for _, issue_id in issue_registry.issues
        if issue_id.startswith("entity_own_area_without_own_name")
    ]


async def test_zha_group_entity_name_migrated_only_once(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a name given to the entity after the move is kept later on.

    The group device is created again when the group regrows after shrinking,
    and when the config entry is reloaded the existing device is found again.
    """
    config_entry.add_to_hass(hass)
    _, legacy_entry = _add_legacy_group_entity(
        zigpy_app_controller_with_group,
        config_entry,
        device_registry,
        entity_registry,
        "My kitchen group",
    )
    await setup_zha()

    entity_registry.async_update_entity(legacy_entry.entity_id, name="Lights")

    group = zigpy_app_controller_with_group.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    member = next(iter(group.values()))
    group.remove_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)
    group.add_member(member)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = entity_registry.async_get(legacy_entry.entity_id)
    assert entry is not None
    assert entry.name == "Lights"
    assert entry.device_id is not None
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.name_by_user == "My kitchen group"


def _add_light_members(
    app_controller: ControllerApplication,
    zigpy_device_mock: Callable[..., zigpy.device.ZigbeeDevice],
) -> None:
    """Add two lights to the group, so it also gets a light group entity."""
    group = app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    for ieee in ("01:2d:6f:00:0a:90:69:f1", "01:2d:6f:00:0a:90:69:f2"):
        light = zigpy_device_mock(
            {
                1: {
                    SIG_EP_INPUT: [
                        general.OnOff.cluster_id,
                        general.LevelControl.cluster_id,
                        general.Basic.cluster_id,
                        general.Groups.cluster_id,
                    ],
                    SIG_EP_OUTPUT: [],
                    SIG_EP_TYPE: zha.DeviceType.DIMMABLE_LIGHT,
                    SIG_EP_PROFILE: zha.PROFILE_ID,
                }
            },
            ieee=ieee,
        )
        app_controller.devices[light.ieee] = light
        group.add_member(light.endpoints[1], suppress_event=True)


@pytest.mark.parametrize(
    ("light_area", "device_area"),
    [
        pytest.param("Kitchen", "Kitchen", id="same_area"),
        pytest.param("Office", None, id="different_areas"),
    ],
)
async def test_zha_group_entity_areas_migrated_with_several_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    zigpy_device_mock: Callable[..., zigpy.device.ZigbeeDevice],
    config_entry: MockConfigEntry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    light_area: str,
    device_area: str | None,
) -> None:
    """Test group entity areas only move to the device when they agree.

    Entities that keep an area of their own without a name of their own are
    reported by core as a repair issue.
    """
    _add_light_members(zigpy_app_controller_with_group, zigpy_device_mock)
    config_entry.add_to_hass(hass)
    coordinator_device, switch_entry = _add_legacy_group_entity(
        zigpy_app_controller_with_group,
        config_entry,
        device_registry,
        entity_registry,
        None,
    )
    light_entry = entity_registry.async_get_or_create(
        "light",
        zha_const.DOMAIN,
        f"light_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
        config_entry=config_entry,
        device_id=coordinator_device.id,
        original_name="Test Group",
    )
    areas = {
        name: area_registry.async_create(name).id for name in ("Kitchen", "Office")
    }
    entity_registry.async_update_entity(
        switch_entry.entity_id, area_id=areas["Kitchen"]
    )
    entity_registry.async_update_entity(
        light_entry.entity_id, area_id=areas[light_area]
    )

    await setup_zha()

    group_proxy = get_zha_gateway_proxy(hass).group_proxies[
        FIXTURE_GRP_WITH_ENTITIES_ID
    ]
    assert group_proxy.device_id is not None
    device = device_registry.async_get(group_proxy.device_id)
    assert device is not None
    expected_device_area = None if device_area is None else areas[device_area]
    assert device.area_id == expected_device_area
    for entry, area_name in ((switch_entry, "Kitchen"), (light_entry, light_area)):
        migrated_entry = entity_registry.async_get(entry.entity_id)
        assert migrated_entry is not None
        assert migrated_entry.area_id == (
            None if expected_device_area is not None else areas[area_name]
        )
    own_area_issues = [
        issue_id
        for _, issue_id in issue_registry.issues
        if issue_id.startswith("entity_own_area_without_own_name")
    ]
    assert len(own_area_issues) == (0 if expected_device_area is not None else 2)


async def test_zha_group_entity_name_not_migrated_with_several_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    zigpy_device_mock: Callable[..., zigpy.device.ZigbeeDevice],
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no name moves to the device of a group with several group entities."""
    app_controller = zigpy_app_controller_with_group
    _add_light_members(app_controller, zigpy_device_mock)

    config_entry.add_to_hass(hass)
    _, legacy_entry = _add_legacy_group_entity(
        app_controller,
        config_entry,
        device_registry,
        entity_registry,
        "My kitchen group",
    )
    await setup_zha()

    group_proxy = get_zha_gateway_proxy(hass).group_proxies[
        FIXTURE_GRP_WITH_ENTITIES_ID
    ]
    assert len(group_proxy.group.group_entities) == 2
    assert group_proxy.device_id is not None
    device = device_registry.async_get(group_proxy.device_id)
    assert device is not None
    assert device.name_by_user is None
    entry = entity_registry.async_get(legacy_entry.entity_id)
    assert entry is not None
    assert entry.device_id == group_proxy.device_id
    assert entry.name == "My kitchen group"


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
    zigpy_device_mock: Callable[..., zigpy.device.ZigbeeDevice],
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


async def test_entity_registry_update_for_device_without_proxy(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a registry update for an entity of a device without a proxy is ignored."""
    await setup_zha()

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(zha_const.DOMAIN, "00:11:22:33:44:55:66:77")},
    )
    entity = entity_registry.async_get_or_create(
        "sensor",
        zha_const.DOMAIN,
        "unknown_device_sensor",
        config_entry=config_entry,
        device_id=device.id,
    )

    # An exception in the listener task fails the test at teardown
    entity_registry.async_update_entity(
        entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
