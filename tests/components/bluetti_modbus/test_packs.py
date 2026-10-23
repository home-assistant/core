"""Tests for the BLUETTI Modbus expansion packs."""

from unittest.mock import patch

from bluetti_modbus_lib import AGGREGATE_SLAVE_ID
from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetti_modbus.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import SERIAL

# The three-pack Balco 260 of bluetti-community/bluetti-modbus#55: the built-in
# pack and three BC260 packs, the one at unit 41 not reporting.
PACK_COUNT_ADDRESS = 51001
PACK_2_SOC_ENTITY = "sensor.pack_2_battery_soc"
PACK_3_SOC_ENTITY = "sensor.pack_3_battery_soc"
PACK_4_SOC_ENTITY = "sensor.pack_4_battery_soc"


@pytest.fixture
def three_packs(
    mock_modbus_connection: MockModbusConnection, mock_modbus_unit: MockModbusUnit
) -> None:
    """Attach the three expansion packs, and count them in the pack summary.

    Depends on the seeded unit so the pack count is set after the summary.
    """
    for unit_id, registers in load_json_object_fixture(
        "balco260_expansion_packs_registers.json", DOMAIN
    ).items():
        mock_modbus_connection.for_unit(int(unit_id)).load_raw(registers)
    mock_modbus_connection.for_unit(AGGREGATE_SLAVE_ID).holding[PACK_COUNT_ADDRESS] = 4


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("three_packs", "entity_registry_enabled_by_default")
async def test_expansion_packs(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Each expansion pack is a device of its own, under the power station."""
    await setup_integration(hass, mock_config_entry)

    main = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert main is not None
    packs = [
        device
        for device in dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        if device.via_device_id == main.id
    ]
    assert sorted(packs, key=lambda device: device.name or "") == snapshot(
        name="devices"
    )
    for device in packs:
        for entity in er.async_entries_for_device(entity_registry, device.id):
            assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.usefixtures("three_packs")
async def test_silent_pack_is_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A pack that answers only its serial number is unavailable, not 0 %."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(PACK_2_SOC_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get(PACK_3_SOC_ENTITY)
    assert state is not None
    assert state.state == "85"


@pytest.mark.usefixtures("three_packs")
async def test_pack_that_stops_answering(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A pack that stops answering goes unavailable alone, then comes back."""
    await setup_integration(hass, mock_config_entry)

    pack = mock_modbus_connection.for_unit(43)
    pack.fail_requests(ModbusTimeoutError("timed out"))
    await _tick(hass, freezer)

    state = hass.states.get(PACK_4_SOC_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get(PACK_3_SOC_ENTITY)
    assert state is not None
    assert state.state == "85"

    pack.fail_requests(None)
    await _tick(hass, freezer)

    state = hass.states.get(PACK_4_SOC_ENTITY)
    assert state is not None
    assert state.state == "79"


@pytest.mark.usefixtures("three_packs")
async def test_pack_count_change_reloads(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A pack added or removed reloads the entry to update its devices."""
    await setup_integration(hass, mock_config_entry)

    summary = mock_modbus_connection.for_unit(AGGREGATE_SLAVE_ID)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _tick(hass, freezer)
        reload.assert_not_called()

        summary.holding[PACK_COUNT_ADDRESS] = 3
        await _tick(hass, freezer)

    reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.parametrize("count", [1, 0])
async def test_no_expansion_pack_is_not_read(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    count: int,
) -> None:
    """With no expansion pack counted, no expansion slot is read."""
    summary = mock_modbus_connection.for_unit(AGGREGATE_SLAVE_ID)
    summary.holding[PACK_COUNT_ADDRESS] = count
    await setup_integration(hass, mock_config_entry)

    for unit_id in range(41, 46):
        assert not mock_modbus_connection.for_unit(unit_id).read_events


@pytest.mark.usefixtures("three_packs")
async def test_remove_a_pack_that_is_gone(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A pack no longer attached can be removed, an attached one cannot."""
    assert await async_setup_component(hass, "config", {})
    await setup_integration(hass, mock_config_entry)
    gone = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, "9999")}
    )
    attached = device_registry.async_get_device_by_identifier(
        (DOMAIN, "4201"), mock_config_entry.entry_id
    )
    assert attached is not None
    main = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert main is not None

    client = await hass_ws_client(hass)
    for device, removable in ((gone, True), (attached, False), (main, False)):
        response = await client.remove_device(device.id)
        assert response["success"] is removable
