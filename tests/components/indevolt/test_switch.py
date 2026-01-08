"""Tests the Indevolt switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch registration for switches."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a switch."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call
    mock_indevolt.set_data = AsyncMock(return_value={"success": True})

    entity_id = "switch.indevolt_cms_sf2000_grid_charging"

    # Verify initial state
    state = hass.states.get(entity_id)
    assert state is not None

    # Turn on the switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_indevolt.set_data.assert_called_once_with("1143", 1)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a switch."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call
    mock_indevolt.set_data = AsyncMock(return_value={"success": True})

    entity_id = "switch.indevolt_cms_sf2000_grid_charging"

    # Turn off the switch
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_indevolt.set_data.assert_called_once_with("1143", 0)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch_turn_on_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when turning on a switch."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call to raise an exception
    mock_indevolt.set_data = AsyncMock(side_effect=Exception("API Error"))

    entity_id = "switch.indevolt_cms_sf2000_grid_charging"

    # Attempt to turn on the switch - should raise exception
    with pytest.raises(Exception, match="API Error"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # Verify API was called
    mock_indevolt.set_data.assert_called_once_with("1143", 1)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_switch_turn_off_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when turning off a switch."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call to raise an exception
    mock_indevolt.set_data = AsyncMock(side_effect=Exception("API Error"))

    entity_id = "switch.indevolt_cms_sf2000_grid_charging"

    # Attempt to turn off the switch - should raise exception
    with pytest.raises(Exception, match="API Error"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # Verify API was called
    mock_indevolt.set_data.assert_called_once_with("1143", 0)
