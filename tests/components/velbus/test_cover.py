"""Velbus cover platform tests."""

<<<<<<< HEAD
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    Platform,
)
=======
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
>>>>>>> 0367f99dae9 (add first velbsu cover test)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.COVER]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


<<<<<<< HEAD
@pytest.mark.parametrize(
    ("entity_id", "entity_num"),
    [
        ("cover.covername", 0),
        ("cover.covernamenopos", 1),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    entity_num: int,
) -> None:
    """Test the cover actions."""
    await init_integration(hass, config_entry)
    entity = config_entry.runtime_data.controller.get_all_cover()[entity_num]
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    entity.close.assert_called_once()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    entity.open.assert_called_once()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    entity.stop.assert_called_once()


async def test_position(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_cover: AsyncMock,
) -> None:
    """Test the set_postion over action."""
    await init_integration(hass, config_entry)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.covername", ATTR_POSITION: 25},
        blocking=True,
    )
    mock_cover.set_position.assert_called_once_with(75)
=======
# async def test_set_target_temperature(
#    hass: HomeAssistant,
#    mock_temperature: AsyncMock,
#    config_entry: MockConfigEntry,
# ) -> None:
#    """Test the target temperature climate action."""
#    await init_integration(hass, config_entry)
#
#    await hass.services.async_call(
#        CLIMATE_DOMAIN,
#        SERVICE_SET_TEMPERATURE,
#        {ATTR_ENTITY_ID: "climate.temperature", ATTR_TEMPERATURE: 29},
#        blocking=True,
#    )
#    mock_temperature.set_temp.assert_called_once_with(29)


# @pytest.mark.parametrize(
#    ("set_mode", "expected_mode"),
#    [
#        (PRESET_AWAY, "night"),
#        (PRESET_COMFORT, "comfort"),
#        (PRESET_ECO, "safe"),
#        (PRESET_HOME, "day"),
#    ],
# )
# async def test_set_preset_mode(
#    hass: HomeAssistant,
#    mock_temperature: AsyncMock,
#    config_entry: MockConfigEntry,
#    set_mode: str,
#    expected_mode: str,
# ) -> None:
# """Test the preset mode climate action."""
#    await init_integration(hass, config_entry)
#    await hass.services.async_call(
#        CLIMATE_DOMAIN,
#        SERVICE_SET_PRESET_MODE,
#        {ATTR_ENTITY_ID: "climate.temperature", ATTR_PRESET_MODE: set_mode},
#        blocking=True,
#    )
#    mock_temperature.set_preset.assert_called_once_with(expected_mode)


# @pytest.mark.parametrize(
#    ("set_mode"),
#    [
#        ("heat"),
#        ("cool"),
#    ],
# )
# async def test_set_hvac_mode(
#    hass: HomeAssistant,
#    mock_temperature: AsyncMock,
#    config_entry: MockConfigEntry,
#    set_mode: str,
# ) -> None:
#    """Test the hvac mode climate action."""
#    await init_integration(hass, config_entry)
#    await hass.services.async_call(
#        CLIMATE_DOMAIN,
#        SERVICE_SET_HVAC_MODE,
#        {ATTR_ENTITY_ID: "climate.temperature", ATTR_HVAC_MODE: set_mode},
#        blocking=True,
#    )
#    mock_temperature.set_mode.assert_called_once_with(set_mode)


# async def test_set_hvac_mode_invalid(
#    hass: HomeAssistant,
#    mock_temperature: AsyncMock,
#    config_entry: MockConfigEntry,
# ) -> None:
#    """Test the hvac mode climate action with an invalid mode."""
#    await init_integration(hass, config_entry)
#    with pytest.raises(ServiceValidationError):
#        await hass.services.async_call(
#            CLIMATE_DOMAIN,
#            SERVICE_SET_HVAC_MODE,
#            {ATTR_ENTITY_ID: "climate.temperature", ATTR_HVAC_MODE: "auto"},
#            blocking=True,
#        )
# mock_temperature.set_mode.assert_not_called()
>>>>>>> 0367f99dae9 (add first velbsu cover test)
