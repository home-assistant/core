"""Tests for the La Marzocco select entities."""

from unittest.mock import MagicMock

from pylamarzocco.const import (
    ModelName,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
)
from pylamarzocco.exceptions import RequestNotSuccessful
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

pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("device_fixture", [ModelName.LINEA_MICRA])
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

    mock_lamarzocco.set_steam_level.assert_called_once_with(
        level=SteamTargetLevel.LEVEL_2
    )


@pytest.mark.parametrize(
    "device_fixture",
    [ModelName.GS3_AV, ModelName.GS3_MP, ModelName.LINEA_MINI],
)
async def test_steam_boiler_level_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure the La Marzocco Steam Level Select is not created for non-Micra models."""
    serial_number = mock_lamarzocco.serial_number
    state = hass.states.get(f"select.{serial_number}_steam_level")

    assert state is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "device_fixture",
    [ModelName.LINEA_MICRA, ModelName.GS3_AV, ModelName.LINEA_MINI],
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

    mock_lamarzocco.set_pre_extraction_mode.assert_called_once_with(
        mode=PreExtractionMode.PREBREWING
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "device_fixture",
    [ModelName.GS3_MP],
)
async def test_pre_brew_infusion_select_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure GS3 MP has no prebrew models."""
    serial_number = mock_lamarzocco.serial_number
    state = hass.states.get(f"select.{serial_number}_prebrew_infusion_mode")

    assert state is None


@pytest.mark.usefixtures("init_integration")
async def test_smart_standby_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lamarzocco: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco Smart Standby mode select."""

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"select.{serial_number}_smart_standby_mode")

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.{serial_number}_smart_standby_mode",
            ATTR_OPTION: "last_brewing",
        },
        blocking=True,
    )

    mock_lamarzocco.set_smart_standby.assert_called_once_with(
        enabled=True, mode=SmartStandByType.LAST_BREW, minutes=10
    )


@pytest.mark.usefixtures("init_integration")
async def test_select_errors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test select errors."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"select.{serial_number}_prebrew_infusion_mode")
    assert state

    mock_lamarzocco.set_pre_extraction_mode.side_effect = RequestNotSuccessful("Boom")

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
