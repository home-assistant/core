"""Tests for the La Marzocco select entities."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.const import (
    MachineModel,
    PhysicalKey,
    PrebrewMode,
    SmartStandbyMode,
    SteamLevel,
)
from pylamarzocco.exceptions import RequestNotSuccessful
from pylamarzocco.models import LaMarzoccoScale
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

from . import async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed

pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("init_integration")
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


@pytest.mark.usefixtures("init_integration")
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


@pytest.mark.usefixtures("init_integration")
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
            ATTR_OPTION: "power_on",
        },
        blocking=True,
    )

    mock_lamarzocco.set_smart_standby.assert_called_once_with(
        enabled=True, mode=SmartStandbyMode.POWER_ON, minutes=10
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


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_active_bbw_recipe(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lamarzocco: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco active bbw recipe select."""

    state = hass.states.get("select.lmz_123a45_active_brew_by_weight_recipe")

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.lmz_123a45_active_brew_by_weight_recipe",
            ATTR_OPTION: "b",
        },
        blocking=True,
    )

    mock_lamarzocco.set_active_bbw_recipe.assert_called_once_with(PhysicalKey.B)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "device_fixture",
    [MachineModel.GS3_AV, MachineModel.GS3_MP, MachineModel.LINEA_MICRA],
)
async def test_other_models_no_active_bbw_select(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure the other models don't have a battery sensor."""

    state = hass.states.get("select.lmz_123a45_active_brew_by_weight_recipe")
    assert state is None


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_active_bbw_select_on_new_scale_added(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure the active bbw select for a new scale is added automatically."""

    mock_lamarzocco.config.scale = None
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("select.scale_123a45_active_brew_by_weight_recipe")
    assert state is None

    mock_lamarzocco.config.scale = LaMarzoccoScale(
        connected=True, name="Scale-123A45", address="aa:bb:cc:dd:ee:ff", battery=50
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("select.scale_123a45_active_brew_by_weight_recipe")
    assert state
