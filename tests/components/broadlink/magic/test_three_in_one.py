"""Tests for BroadLink Magic three-in-one thermostat panels."""

from unittest.mock import AsyncMock

from broadlink_async.magic import MSG_HEARTBEAT, Family, ImportedDevice, pack_message
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.entity import PENDING_COMMAND_TIMEOUT
from homeassistant.components.climate import HVACMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("socket_enabled")

PANEL_ADDR = 11
STATUS = bytes.fromhex("77121a210014171100000000002800")
CAPABILITIES = bytes.fromhex("1e1023316307000000000000000000")


@pytest.fixture
def family(family: Family) -> Family:
    """Return the test family with a three-in-one thermostat panel."""
    family.devices.append(
        ImportedDevice(
            did="00000000000000000000aabbccddeeff",
            pid="0000000000000000000000008baf0000",
            name="Thermostat",
            sdid="0000000000000000000002ab3cfdd307",
            spid="000000000000000000000000bbaf0000",
            short_addr=PANEL_ADDR,
            ble_category="BLEAC",
            room_id=1,
        )
    )
    return family


def _entity_id(entity_registry: er.EntityRegistry, domain: str, suffix: str) -> str:
    entity_id = entity_registry.async_get_entity_id(
        domain, DOMAIN, f"family-1_0000000000000000000002ab3cfdd307{suffix}"
    )
    assert entity_id is not None
    return entity_id


async def test_three_in_one_panel(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the AC and floor-heating loads of one panel."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    ac = _entity_id(entity_registry, "climate", "")
    floor = _entity_id(entity_registry, "climate", "_floor_heating")
    ac_entry = entity_registry.async_get(ac)
    assert ac_entry is not None
    assert ac_entry.device_id is not None
    floor_entry = entity_registry.async_get(floor)
    assert floor_entry is not None
    assert floor_entry.device_id == ac_entry.device_id
    panel = device_registry.async_get(ac_entry.device_id)
    assert panel is not None
    assert panel.model == "Magic Home 3-in-1 Thermostat"

    coordinator = config_entry.runtime_data
    coordinator.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    coordinator._handle_fastcon_report(PANEL_ADDR, STATUS)
    await hass.async_block_till_done()

    ac_state = hass.states.get(ac)
    assert ac_state is not None
    assert ac_state.state == HVACMode.COOL
    assert ac_state.attributes["temperature"] == 26
    assert ac_state.attributes["current_temperature"] == 20
    assert ac_state.attributes["fan_mode"] == "low"
    floor_state = hass.states.get(floor)
    assert floor_state is not None
    assert floor_state.state == HVACMode.HEAT
    assert floor_state.attributes["temperature"] == 23
    assert floor_state.attributes["current_temperature"] == 20

    coordinator._handle_fastcon_report(PANEL_ADDR, CAPABILITIES)
    await hass.async_block_till_done()
    assert hass.states.get(ac).attributes["temperature"] == 26

    async def assert_sent(
        domain: str, service: str, data: dict[str, object], payloads: list[bytes]
    ) -> None:
        mock_send.reset_mock()
        await hass.services.async_call(domain, service, data, blocking=True)
        assert mock_send.await_args.args == (PANEL_ADDR, payloads)

    await assert_sent(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: floor, "temperature": 28},
        [b"\x04\x01\x1c"],
    )
    await assert_sent("climate", "turn_off", {ATTR_ENTITY_ID: floor}, [b"\x00\x01\x02"])
    coordinator._handle_fastcon_report(PANEL_ADDR, STATUS)
    await hass.async_block_till_done()
    floor_state = hass.states.get(floor)
    assert floor_state.state == HVACMode.OFF
    assert floor_state.attributes["temperature"] == 28
    coordinator._handle_fastcon_report(
        PANEL_ADDR, bytes.fromhex("75121a2100141c11") + bytes(7)
    )
    await hass.async_block_till_done()
    assert hass.states.get(floor).state == HVACMode.OFF
    await assert_sent("climate", "turn_on", {ATTR_ENTITY_ID: floor}, [b"\x00\x01\x03"])
    assert hass.states.get(floor).state == HVACMode.HEAT

    await assert_sent(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ac, "temperature": 25},
        [b"\x02\x01\x19"],
    )


async def test_set_temperature_applies_hvac_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a temperature request with an HVAC mode also turns the load on."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    ac = _entity_id(entity_registry, "climate", "")
    floor = _entity_id(entity_registry, "climate", "_floor_heating")
    config_entry.runtime_data.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )
    config_entry.runtime_data.async_set_updated_data(
        config_entry.runtime_data.gateway_set
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: floor, "temperature": 22, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert [call.args for call in mock_send.await_args_list] == [
        (PANEL_ADDR, [b"\x00\x01\x03"]),
        (PANEL_ADDR, [b"\x04\x01\x16"]),
    ]
    floor_state = hass.states.get(floor)
    assert floor_state.state == HVACMode.HEAT
    assert floor_state.attributes["temperature"] == 22

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ac, "temperature": 25, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    assert len(mock_send.await_args_list) == 2
    assert mock_send.await_args_list[-1].args == (PANEL_ADDR, [b"\x02\x01\x19"])
    ac_state = hass.states.get(ac)
    assert ac_state.state == HVACMode.COOL
    assert ac_state.attributes["temperature"] == 25


async def test_unconfirmed_command_expires(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a lost command stops hiding device reports after a while."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    floor = _entity_id(entity_registry, "climate", "_floor_heating")
    coordinator = config_entry.runtime_data
    coordinator.gateway_set.handle_packet(
        "aabbccddeeff",
        pack_message(MSG_HEARTBEAT, 1, bytes.fromhex("aabbccddeeff")),
        ("192.0.2.10", 41001),
    )

    await hass.services.async_call(
        "climate", "turn_off", {ATTR_ENTITY_ID: floor}, blocking=True
    )
    coordinator._handle_fastcon_report(PANEL_ADDR, STATUS)
    await hass.async_block_till_done()
    assert hass.states.get(floor).state == HVACMode.OFF

    freezer.tick(PENDING_COMMAND_TIMEOUT)
    coordinator._handle_fastcon_report(PANEL_ADDR, STATUS)
    await hass.async_block_till_done()
    assert hass.states.get(floor).state == HVACMode.HEAT
