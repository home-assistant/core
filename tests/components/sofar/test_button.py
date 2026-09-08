"""Test the Sofar Inverter Modbus button platform."""

from collections.abc import Callable, Sequence
from unittest.mock import patch

from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
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


async def _setup(
    hass: HomeAssistant,
    serial: str,
    model: str,
    seed: Callable[[MockModbusUnit], None],
    platforms: Sequence[Platform] = (Platform.BUTTON,),
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up an inverter with the given platforms loaded."""
    connection = MockModbusConnection()
    seed(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=serial, data=MOCK_USER_INPUT, title=model
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.sofar.PLATFORMS", list(platforms)),
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
async def test_pv_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a PV-only inverter only gets the RTC sync button."""
    entry, _ = await _setup(hass, MOCK_SERIAL, MOCK_MODEL, seed_pv_inverter)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hybrid_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a hybrid inverter gets both buttons."""
    entry, _ = await _setup(
        hass, MOCK_HYBRID_SERIAL, MOCK_HYBRID_MODEL, seed_hybrid_inverter
    )
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("key", "register"),
    [
        pytest.param("rtc_sync", 0x100A, id="rtc_sync"),
        pytest.param("iv_curve_scan", 0x1027, id="iv_curve_scan"),
    ],
)
async def test_button_press(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, key: str, register: int
) -> None:
    """Test pressing a button writes its trigger register."""
    _, connection = await _setup(
        hass, MOCK_HYBRID_SERIAL, MOCK_HYBRID_MODEL, seed_hybrid_inverter
    )
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_{key}"
    )
    assert entity_id is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert connection.for_unit(1).holding[register] == 1


async def test_rtc_sync_reported_to_hass(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the RTC sync result reaches its sensor after the refresh."""
    await _setup(
        hass,
        MOCK_HYBRID_SERIAL,
        MOCK_HYBRID_MODEL,
        seed_hybrid_inverter,
        platforms=(Platform.BUTTON, Platform.SENSOR),
    )
    button_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_rtc_sync"
    )
    result_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_sync_rtc_result"
    )
    assert button_id is not None
    assert result_id is not None
    assert (state := hass.states.get(result_id)) is not None
    assert state.state == "successful"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: button_id},
        blocking=True,
    )

    assert (state := hass.states.get(result_id)) is not None
    assert state.state == "operation_in_progress"


async def test_press_modbus_error(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a write failure propagates as-is."""
    _, connection = await _setup(hass, MOCK_SERIAL, MOCK_MODEL, seed_pv_inverter)
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_rtc_sync"
    )
    assert entity_id is not None
    connection.for_unit(1).fail_write(0x1004, ModbusError("busy"))

    with pytest.raises(ModbusError, match="busy"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
