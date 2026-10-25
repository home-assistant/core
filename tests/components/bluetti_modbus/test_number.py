"""Tests for the BLUETTI Modbus numbers."""

import asyncio
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetti_modbus.const import SCAN_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SERIAL_ADDRESS

DISCHARGE_LIMIT_ENTITY = "number.balco_260_discharge_limit"
DISCHARGE_LIMIT_ADDRESS = 57016
CHARGE_LIMIT_ENTITY = "number.balco_260_charge_limit"
CHARGE_LIMIT_ADDRESS = 57017


@pytest.mark.usefixtures("mock_modbus_unit")
@patch("homeassistant.components.bluetti_modbus.PLATFORMS", [Platform.NUMBER])
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All number entities and their states match the snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_writes_the_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Setting a value writes the register, and the state follows at once."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
        blocking=True,
    )

    assert mock_modbus_unit.holding[DISCHARGE_LIMIT_ADDRESS] == 20
    entity = hass.states.get(DISCHARGE_LIMIT_ENTITY)
    assert entity is not None
    assert entity.state == "20"


async def _let_tasks_run() -> None:
    """Let the pending tasks run as far as they can without blocking."""
    for _ in range(20):
        await asyncio.sleep(0)


async def test_queued_write_is_dropped_for_another_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A write waiting its turn is not sent once another device answers."""
    await setup_integration(hass, mock_config_entry)
    write_register = mock_modbus_unit.write_register
    release = asyncio.Event()
    written: list[int] = []

    async def held_write(address: int, value: int) -> None:
        written.append(address)
        await release.wait()
        await write_register(address, value)

    with patch.object(mock_modbus_unit, "write_register", held_write):
        first = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: CHARGE_LIMIT_ENTITY, ATTR_VALUE: 95},
                blocking=True,
            )
        )
        # Waits for the first one: the platform takes one action at a time.
        second = hass.async_create_task(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: DISCHARGE_LIMIT_ENTITY, ATTR_VALUE: 20},
                blocking=True,
            )
        )
        await _let_tasks_run()
        assert written == [CHARGE_LIMIT_ADDRESS]

        mock_modbus_unit.holding[SERIAL_ADDRESS] = 1
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await _let_tasks_run()

        release.set()
        await first
        with pytest.raises(HomeAssistantError, match="setting was not written"):
            await second

    assert written == [CHARGE_LIMIT_ADDRESS]
