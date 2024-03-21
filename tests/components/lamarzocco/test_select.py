"""Tests for the La Marzocco select entities."""

from unittest.mock import MagicMock

from lmcloud.const import LaMarzoccoModel
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize("device_fixture", [LaMarzoccoModel.LINEA_MICRA])
async def test_steam_boiler_level(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lamarzocco: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Steam Level Select (only for Micra Models)."""

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"select.{serial_number}_steam_level")

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    # on/off service calls
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.{serial_number}_steam_level",
            ATTR_OPTION: "1",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_level.mock_calls) == 1
    mock_lamarzocco.set_steam_level.assert_called_once_with(1, None)


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.GS3_AV, LaMarzoccoModel.GS3_MP, LaMarzoccoModel.LINEA_MINI],
)
async def test_steam_boiler_level_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure the La Marzocco Steam Level Select is not created for non-Micra models."""
    serial_number = mock_lamarzocco.serial_number
    state = hass.states.get(f"select.{serial_number}_steam_level")

    assert state is None


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.LINEA_MICRA, LaMarzoccoModel.GS3_AV, LaMarzoccoModel.LINEA_MINI],
)
async def test_pre_brew_infusion_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lamarzocco: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Prebrew/-infusion select."""

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"select.{serial_number}_prebrew_infusion_mode")

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    # on/off service calls
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.{serial_number}_prebrew_infusion_mode",
            ATTR_OPTION: "preinfusion",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.select_pre_brew_infusion_mode.mock_calls) == 1
    mock_lamarzocco.select_pre_brew_infusion_mode.assert_called_once_with(
        mode="Preinfusion"
    )


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.GS3_MP],
)
async def test_pre_brew_infusion_select_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure the La Marzocco Steam Level Select is not created for non-Micra models."""
    serial_number = mock_lamarzocco.serial_number
    state = hass.states.get(f"select.{serial_number}_prebrew_infusion_mode")

    assert state is None
