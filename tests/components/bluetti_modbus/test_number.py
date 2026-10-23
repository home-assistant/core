"""Tests for the BLUETTI Modbus numbers."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

DISCHARGE_LIMIT_ENTITY = "number.balco_260_discharge_limit"
DISCHARGE_LIMIT_ADDRESS = 57016


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
