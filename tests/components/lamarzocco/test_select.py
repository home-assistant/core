"""Tests for the La Marzocco select entities."""

from unittest.mock import MagicMock

from lmcloud.const import MachineModel, PrebrewMode, SteamLevel
from lmcloud.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MICRA])
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
            ATTR_OPTION: "2",
        },
        blocking=True,
    )

    mock_lamarzocco.set_steam_level.assert_called_once_with(level=SteamLevel.LEVEL_2)


@pytest.mark.parametrize(
    "device_fixture",
    [MachineModel.GS3_AV, MachineModel.GS3_MP, MachineModel.LINEA_MINI],
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
    [MachineModel.LINEA_MICRA, MachineModel.GS3_AV, MachineModel.LINEA_MINI],
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
            ATTR_OPTION: "prebrew",
        },
        blocking=True,
    )

    mock_lamarzocco.set_prebrew_mode.assert_called_once_with(mode=PrebrewMode.PREBREW)


@pytest.mark.parametrize(
    "device_fixture",
    [MachineModel.GS3_MP],
)
async def test_pre_brew_infusion_select_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure the La Marzocco Steam Level Select is not created for non-Micra models."""
    serial_number = mock_lamarzocco.serial_number
    state = hass.states.get(f"select.{serial_number}_prebrew_infusion_mode")

    assert state is None


async def test_select_errors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test select errors."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"select.{serial_number}_prebrew_infusion_mode")
    assert state

    mock_lamarzocco.set_prebrew_mode.side_effect = RequestNotSuccessful("Boom")

    # Test setting invalid option
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: f"select.{serial_number}_prebrew_infusion_mode",
                ATTR_OPTION: "prebrew",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "select_option_error"
