"""Tests for the Flexit Nordic (BACnet) climate entity."""

from unittest.mock import AsyncMock

from flexit_bacnet import VENTILATION_MODE_AWAY, VENTILATION_MODE_HOME
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    PRESET_AWAY,
    PRESET_HOME,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.components.flexit_bacnet.const import PRESET_TO_VENTILATION_MODE_MAP
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.device_name"


async def test_climate_entity(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_hvac_preset_mode(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set preset mode to away
    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_AWAY
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    mock_flexit_bacnet.set_ventilation_mode.assert_called_once_with(
        PRESET_TO_VENTILATION_MODE_MAP[PRESET_AWAY]
    )

    # Set preset mode to home
    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_HOME
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: PRESET_HOME,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOME

    mock_flexit_bacnet.set_ventilation_mode.assert_called_with(
        PRESET_TO_VENTILATION_MODE_MAP[PRESET_HOME]
    )
