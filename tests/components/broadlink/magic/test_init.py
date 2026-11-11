"""Tests for BroadLink Magic setup and remote entities."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from broadlink_async.magic import MSG_HEARTBEAT, ImportedDevice, pack_message
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.broadlink.const import (
    BROADLINK_DATA,
    DOMAIN,
    UPDATE_INTERVAL,
    BroadlinkData,
)
from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from .. import get_device

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_classic_and_magic_entries_coexist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup dispatches classic and Magic entries under one domain."""
    hass.data[BROADLINK_DATA] = BroadlinkData()
    config_entry.add_to_hass(hass)
    classic_entry = get_device("Office").get_mock_entry()
    classic_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.broadlink._async_setup_magic_entry",
            new_callable=AsyncMock,
        ) as setup_magic,
        patch(
            "homeassistant.components.broadlink.BroadlinkDevice.async_setup",
            new_callable=AsyncMock,
            return_value=True,
        ) as setup_classic,
        patch(
            "homeassistant.components.broadlink.BroadlinkHeartbeat.async_setup",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    setup_magic.assert_awaited_once_with(hass, config_entry)
    setup_classic.assert_awaited_once()
    assert "entry_kind" not in classic_entry.data


async def test_setup_devices_remote_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test family setup, device topology, remote command, and unload."""
    config_entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "stale-device")},
        name="Stale device",
    )
    stale_entity = entity_registry.async_get_or_create(
        "light",
        DOMAIN,
        "stale-entity",
        config_entry=config_entry,
        device_id=stale_device.id,
        suggested_object_id="stale",
    )
    stale_group_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "magic:dev:family-1_group_65")},
        name="Old light group",
    )
    stale_group_entity = entity_registry.async_get_or_create(
        "light",
        DOMAIN,
        "family-1_group_65_light",
        config_entry=config_entry,
        device_id=stale_group_device.id,
        suggested_object_id="old_light_group",
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(stale_entity.entity_id) is None
    assert entity_registry.async_get(stale_group_entity.entity_id) is None
    assert device_registry.async_get(stale_device.id) is None
    assert device_registry.async_get(stale_group_device.id) is None
    family_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "magic:family:family-1"), config_entry_id=config_entry.entry_id
    )
    assert family_device is not None
    whole_home_area = area_registry.async_get_area_by_name("Whole home")
    assert whole_home_area is not None
    assert family_device.area_id == whole_home_area.id
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "magic:gw:aabbccddeeff"), config_entry_id=config_entry.entry_id
        )
        is not None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "magic:gw:112233445566"), config_entry_id=config_entry.entry_id
        )
        is not None
    )
    climate_state = hass.states.get("climate.whole_home_air_conditioner")
    assert climate_state is not None
    assert climate_state.attributes["target_temp_step"] == 1.0
    assert hass.states.get("light.living_room_lamp") is not None
    assert hass.states.get("light.living_room_living_room_lights") is None
    assert hass.states.get("light.living_room_all_lights") is None
    switch_channel_1 = entity_registry.async_get_entity_id(
        "switch",
        DOMAIN,
        "family-1_aabbccddeeff_4_0",
    )
    switch_channel_2 = entity_registry.async_get_entity_id(
        "switch",
        DOMAIN,
        "family-1_aabbccddeeff_4_1",
    )
    assert switch_channel_1 is not None
    assert switch_channel_2 is not None
    assert (
        hass.states.get(switch_channel_1).attributes["friendly_name"]
        == "Wall panel Left key"
    )
    assert (
        hass.states.get(switch_channel_2).attributes["friendly_name"]
        == "Wall panel Channel 2"
    )
    living_room_area = area_registry.async_get_area_by_name("Living room")
    assert living_room_area is not None
    climate_entity = entity_registry.async_get("climate.whole_home_air_conditioner")
    assert climate_entity is not None
    assert climate_entity.device_id is not None
    climate_device = device_registry.async_get(climate_entity.device_id)
    assert climate_device is not None
    assert climate_device.area_id == whole_home_area.id
    lamp_entity = entity_registry.async_get("light.living_room_lamp")
    assert lamp_entity is not None
    assert lamp_entity.device_id is not None
    lamp_device = device_registry.async_get(lamp_entity.device_id)
    assert lamp_device is not None
    assert lamp_device.area_id == living_room_area.id

    coordinator = config_entry.runtime_data
    coordinator.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(
            MSG_HEARTBEAT,
            1,
            bytes.fromhex("aabbccddeeff"),
        ),
        ("192.0.2.10", 41001),
    )
    coordinator.async_set_updated_data(coordinator.gateway_set)
    coordinator._handle_fastcon_report(257, bytes((64, 10, 20, 30, 127, 128)))
    await hass.async_block_till_done()
    assert hass.states.get("light.living_room_lamp").attributes["brightness"] == 128
    coordinator._handle_fastcon_report(6, b"\x01\x02\x1a\x03")
    coordinator._handle_fastcon_report(258, b"\x03\x02")
    await hass.async_block_till_done()
    assert (
        hass.states.get("climate.whole_home_air_conditioner").attributes["temperature"]
        == 26
    )
    assert hass.states.get(switch_channel_1).state == "off"
    assert hass.states.get(switch_channel_2).state == "on"

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: "climate.whole_home_air_conditioner",
            "hvac_mode": HVACMode.COOL,
        },
        blocking=True,
    )
    assert mock_send.await_args.args[0] == 6
    assert mock_send.await_args.args[1] == [
        b"\x00\x01\x01",
        b"\x01\x01\x02",
    ]
    coordinator._handle_fastcon_report(6, b"\x00\x02\x1b\x01")
    await hass.async_block_till_done()
    climate_state = hass.states.get("climate.whole_home_air_conditioner")
    assert climate_state is not None
    assert climate_state.state == HVACMode.COOL

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            ATTR_ENTITY_ID: "climate.whole_home_air_conditioner",
            "temperature": 26,
        },
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x02\x01\x1a"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {
            ATTR_ENTITY_ID: "climate.whole_home_air_conditioner",
            "fan_mode": "high",
        },
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x03\x01\x03"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate",
        "turn_off",
        {ATTR_ENTITY_ID: "climate.whole_home_air_conditioner"},
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x00\x01\x00"]
    coordinator._handle_fastcon_report(6, b"\x01\x02\x1a\x03")
    await hass.async_block_till_done()
    climate_state = hass.states.get("climate.whole_home_air_conditioner")
    assert climate_state is not None
    assert climate_state.state == HVACMode.OFF

    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.living_room_lamp"},
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x00"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: switch_channel_1},
        blocking=True,
    )
    assert mock_send.await_args.args[0] == 258
    assert mock_send.await_args.args[1] == [b"\x01\x01"]
    coordinator.async_set_updated_data(coordinator.gateway_set)
    await hass.async_block_till_done()
    assert hass.states.get(switch_channel_1).state == "on"

    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.living_room_lamp"},
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x80"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            ATTR_ENTITY_ID: "light.living_room_lamp",
            "brightness": 255,
        },
        blocking=True,
    )
    assert mock_send.await_args.args[0] == 257
    assert mock_send.await_args.args[1] == [b"\x7f\x0a\x14\x1e\x00\x00"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            ATTR_ENTITY_ID: "light.living_room_lamp",
            "brightness": 128,
            "rgb_color": [20, 30, 10],
        },
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x40\x0a\x14\x1e\x00\x00"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            ATTR_ENTITY_ID: "light.living_room_lamp",
            "color_temp_kelvin": 6500,
        },
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x40\x00\x00\x00\x00\xff"]

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_send_light(
            ImportedDevice(did="missing", pid="", name="Missing"), b"\x00"
        )
    assert err.value.translation_key == "device_not_addressable"
    mock_send.return_value = 0
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "light",
            "turn_off",
            {ATTR_ENTITY_ID: "light.living_room_lamp"},
            blocking=True,
        )
    assert err.value.translation_key == "gateway_offline"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: "light.living_room_lamp", "rgb_color": [1, 2, 3]},
            blocking=True,
        )
    coordinator.async_set_updated_data(coordinator.gateway_set)
    await hass.async_block_till_done()
    lamp_state = hass.states.get("light.living_room_lamp")
    assert lamp_state.state == "on"
    assert lamp_state.attributes["color_mode"] == "color_temp"

    mock_send.return_value = 1
    coordinator._handle_fastcon_report(257, bytes(6))
    await hass.async_block_till_done()
    assert hass.states.get("light.living_room_lamp").state == "off"
    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.living_room_lamp", "color_temp_kelvin": 6500},
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x40\x00\x00\x00\x00\xff"]
    lamp_state = hass.states.get("light.living_room_lamp")
    assert lamp_state.state == "on"
    assert lamp_state.attributes["brightness"] == 128

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_coordinator_allows_offline_family_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an update succeeds while entities remain unavailable."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert not coordinator.gateway_set.online_gateways
    state = hass.states.get("light.living_room_lamp")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("target", "error", "state"),
    [
        (
            "homeassistant.components.broadlink.FamilyCoordinator."
            "async_config_entry_first_refresh",
            ConfigEntryNotReady,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            RuntimeError,
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_failed_setup_releases_gateway_routes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_gateway_listener: MagicMock,
    target: str,
    error: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test a failed family setup unregisters its gateway routes."""
    config_entry.add_to_hass(hass)
    with patch(target, side_effect=error):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is state
    mock_gateway_listener.register_gateway_set.assert_called_once()
    mock_gateway_listener.async_unregister_entry.assert_awaited_once_with(
        config_entry.entry_id
    )


async def test_gateway_port_unavailable_retries_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a busy gateway port lets Home Assistant retry the family setup."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.broadlink.async_get_gateway_listener",
        side_effect=OSError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_magic_diagnostics_exclude_identifiers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test Magic diagnostics work and leave out tokens and identifiers."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    coordinator.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    coordinator._handle_fastcon_report(258, b"\x03\x02")

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["family"]["devices"] == len(coordinator.family.devices)
    assert diagnostics["gateways"] == [
        {"online": True, "has_peer": True},
        {"online": False, "has_peer": False},
    ]
    panel = next(item for item in diagnostics["devices"] if item["short_addr"] == 258)
    assert panel["kind"] == "switch"
    assert panel["reports"] == 1
    dumped = json.dumps(diagnostics)
    for secret in (
        "aabbccddeeff",
        "112233445566",
        "00010203",
        "00112233445566778899aabbccddeeff",
        "family-1",
        "Test home",
        "Living room",
        "192.0.2.10",
    ):
        assert secret not in dumped


async def test_inbound_gateway_address_is_runtime_only(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a gateway peer change is not persisted in config entry data."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    gateway_set = config_entry.runtime_data.gateway_set
    gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(
            MSG_HEARTBEAT,
            1,
            bytes.fromhex("aabbccddeeff"),
        ),
        ("192.0.2.200", 41001),
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert gateway_set.online_gateways[0].peer == ("192.0.2.200", 41001)
    addresses = {
        gateway["mac"]: gateway["host"] for gateway in config_entry.data["gateways"]
    }
    assert addresses["aabbccddeeff"] == "192.0.2.10"
    assert addresses["112233445566"] == "192.0.2.11"
