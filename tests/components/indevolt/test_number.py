"""Tests the Indevolt number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number registration for numbers."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_set_discharge_limit(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting discharge limit value."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call
    mock_indevolt.set_data = AsyncMock(return_value={"success": True})

    entity_id = "number.indevolt_cms_sf2000_discharge_limit"

    # Set the discharge limit to 50%
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 50},
        blocking=True,
    )

    # Verify API was called with correct parameters (key "1142", value 50)
    mock_indevolt.set_data.assert_called_once_with("1142", 50)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_set_max_ac_output_power(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting max AC output power value."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call
    mock_indevolt.set_data = AsyncMock(return_value={"success": True})

    entity_id = "number.indevolt_cms_sf2000_max_ac_output_power"

    # Set the max AC output power to 2000W (within valid range 0-2400)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 2000},
        blocking=True,
    )

    # Verify API was called with correct parameters (key "1147", value 2000)
    mock_indevolt.set_data.assert_called_once_with("1147", 2000)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_set_inverter_input_limit(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting inverter input limit value."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call
    mock_indevolt.set_data = AsyncMock(return_value={"success": True})

    entity_id = "number.indevolt_cms_sf2000_inverter_input_limit"

    # Set the inverter input limit to 2000W (within valid range 100-2400)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 2000},
        blocking=True,
    )

    # Verify API was called with correct parameters (key "1138", value 2000)
    mock_indevolt.set_data.assert_called_once_with("1138", 2000)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_set_feedin_power_limit(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting feed-in power limit value."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call
    mock_indevolt.set_data = AsyncMock(return_value={"success": True})

    entity_id = "number.indevolt_cms_sf2000_feed_in_power_limit"

    # Set the feed-in power limit to 1500W (within valid range 100-2400)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, "value": 1500},
        blocking=True,
    )

    # Verify API was called with correct parameters (key "1146", value 1500)
    mock_indevolt.set_data.assert_called_once_with("1146", 1500)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_number_set_value_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when setting a number value."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    # Mock the set_data call to raise an exception
    mock_indevolt.set_data = AsyncMock(side_effect=Exception("API Error"))

    entity_id = "number.indevolt_cms_sf2000_discharge_limit"

    # Attempt to set value - should raise exception
    with pytest.raises(Exception, match="API Error"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, "value": 75},
            blocking=True,
        )

    # Verify API was called
    mock_indevolt.set_data.assert_called_once_with("1142", 75)
