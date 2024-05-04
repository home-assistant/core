"""Tests for La Marzocco switches."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("entity_name", "method_name", "args_on", "args_off"),
    [
        ("", "set_power", (True, None), (False, None)),
        (
            "_auto_on_off",
            "set_auto_on_off_global",
            (True,),
            (False,),
        ),
        ("_steam_boiler", "set_steam", (True, None), (False, None)),
    ],
)
async def test_switches(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    method_name: str,
    args_on: tuple,
    args_off: tuple,
) -> None:
    """Test the La Marzocco switches."""
    serial_number = mock_lamarzocco.serial_number

    control_fn = getattr(mock_lamarzocco, method_name)

    state = hass.states.get(f"switch.{serial_number}{entity_name}")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}{entity_name}",
        },
        blocking=True,
    )

    assert len(control_fn.mock_calls) == 1
    control_fn.assert_called_once_with(*args_off)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}{entity_name}",
        },
        blocking=True,
    )

    assert len(control_fn.mock_calls) == 2
    control_fn.assert_called_with(*args_on)


async def test_device(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device for one switch."""

    state = hass.states.get(f"switch.{mock_lamarzocco.serial_number}")
    assert state

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot


async def test_call_without_bluetooth_works(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that if not using bluetooth, the switch still works."""
    serial_number = mock_lamarzocco.serial_number
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator._use_bluetooth = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam.mock_calls) == 1
    mock_lamarzocco.set_steam.assert_called_once_with(False, None)
