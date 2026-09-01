"""Test the Sofar Inverter Modbus select platform."""

from unittest.mock import patch

from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.sofar.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    MOCK_HYBRID_MODEL,
    MOCK_HYBRID_SERIAL,
    MOCK_MODEL,
    MOCK_SERIAL,
    MOCK_USER_INPUT,
    seed_hybrid_inverter,
    seed_pv_inverter,
)

from tests.common import MockConfigEntry, snapshot_platform


async def _setup_hybrid(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up a hybrid inverter with only the select platform loaded."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_USER_INPUT,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.sofar.PLATFORMS", [Platform.SELECT]),
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry, connection


async def _setup_pv(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up a PV-only inverter with only the select platform loaded."""
    connection = MockModbusConnection()
    seed_pv_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT, title=MOCK_MODEL
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.sofar.PLATFORMS", [Platform.SELECT]),
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry, connection


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hybrid_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the select entities a hybrid inverter serves."""
    entry, _ = await _setup_hybrid(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_pv_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a PV-only inverter gets no select entities."""
    entry, _ = await _setup_pv(hass)
    assert er.async_entries_for_config_entry(entity_registry, entry.entry_id) == []


@pytest.mark.parametrize(
    ("key", "initial", "option"),
    [
        pytest.param(
            "charger_use_mode", "self_use", "feed_in_priority_mode", id="charger"
        ),
        pytest.param("eps_control", "turn_off", "turn_on_enable_cold_start", id="eps"),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
    initial: str,
    option: str,
) -> None:
    """Test selecting an option writes it and refreshes the read-back."""
    await _setup_hybrid(hass)
    entity_id = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_{key}"
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == initial

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == option


async def test_select_option_modbus_error(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a write failure propagates as-is."""
    _, connection = await _setup_hybrid(hass)
    charger_id = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_charger_use_mode"
    )
    assert charger_id is not None
    connection.for_unit(1).fail_write(0x1110, ModbusError("busy"))

    with pytest.raises(ModbusError, match="busy"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: charger_id, ATTR_OPTION: "feed_in_priority_mode"},
            blocking=True,
        )
