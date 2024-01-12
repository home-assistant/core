"""Tests for La Marzocco switches."""
from unittest.mock import MagicMock

from lmcloud.const import LaMarzoccoModel
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_main(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Main switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_main")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 1
    mock_lamarzocco.set_power.assert_called_once_with(False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_main",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 2
    mock_lamarzocco.set_power.assert_called_with(True)


async def test_auto_on_off(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Auto On/Off switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_auto_on_off")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 1
    mock_lamarzocco.set_auto_on_off_global.assert_called_once_with(enable=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_auto_on_off_global.mock_calls) == 2
    mock_lamarzocco.set_auto_on_off_global.assert_called_with(enable=True)


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.GS3_AV, LaMarzoccoModel.LINEA_MINI, LaMarzoccoModel.LINEA_MICRA],
)
async def test_prebrew(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Prebrew switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_prebrew")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 1
    mock_lamarzocco.set_prebrew.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_prebrew",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_prebrew.mock_calls) == 2
    mock_lamarzocco.set_prebrew.assert_called_with(enabled=True)


@pytest.mark.parametrize("device_fixture", [LaMarzoccoModel.GS3_MP])
async def test_prebrew_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Assert prebrew switch is None for unsupported models."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_prebrew")
    assert state is None


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.GS3_AV, LaMarzoccoModel.LINEA_MINI, LaMarzoccoModel.LINEA_MICRA],
)
async def test_preinfusion(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Preinfusion switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_preinfusion")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 1
    mock_lamarzocco.set_preinfusion.assert_called_once_with(enabled=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_preinfusion.mock_calls) == 2
    mock_lamarzocco.set_preinfusion.assert_called_with(enabled=False)


@pytest.mark.parametrize("device_fixture", [LaMarzoccoModel.GS3_MP])
async def test_preinfusion_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Assert preinfusion switch is None for unsupported models."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_preinfusion")
    assert state is None


async def test_steam_boiler_enable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Steam Boiler switch."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}_steam_boiler")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam.mock_calls) == 1
    mock_lamarzocco.set_steam.assert_called_once_with(False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam.mock_calls) == 2
    mock_lamarzocco.set_steam.assert_called_with(True)
