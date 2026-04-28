"""Tests for the Indevolt button platform."""

from unittest.mock import AsyncMock, patch

from indevolt_api import IndevoltConfig, IndevoltEnergyMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID_GEN2 = "button.cms_sf2000_enable_standby_mode"
ENTITY_ID_GEN1 = "button.bk1600_enable_standby_mode"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2, 1], indirect=True)
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button entity registration and states."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_button_press_standby(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing the standby button switches to real-time mode and sends standby action."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Mock call to pause (dis)charging
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_ID_GEN2},
        blocking=True,
    )

    # Verify set_data was called for mode switch and stop() was called
    mock_indevolt.set_data.assert_called_once_with(
        IndevoltConfig.WRITE_ENERGY_MODE, IndevoltEnergyMode.REAL_TIME_CONTROL
    )
    mock_indevolt.stop.assert_called_once()


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_button_press_standby_already_in_realtime_mode(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing standby when already in real-time mode skips the mode switch."""

    # Force real-time control mode
    mock_indevolt.fetch_data.return_value[IndevoltConfig.READ_ENERGY_MODE] = (
        IndevoltEnergyMode.REAL_TIME_CONTROL
    )
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Mock call to pause (dis)charging
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_ID_GEN2},
        blocking=True,
    )

    # Verify stop() was called and no mode switch was needed
    mock_indevolt.set_data.assert_not_called()
    mock_indevolt.stop.assert_called_once()


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_button_press_standby_rejected_command(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing standby raises HomeAssistantError when the device rejects the command."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    # Simulate stop() returning False (device rejected the command)
    mock_indevolt.stop.return_value = False

    # Mock call to pause (dis)charging
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_ID_GEN2},
            blocking=True,
        )


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_button_press_standby_portable_mode_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing standby raises HomeAssistantError when device is in outdoor/portable mode."""

    # Force outdoor/portable mode
    mock_indevolt.fetch_data.return_value[IndevoltConfig.READ_ENERGY_MODE] = (
        IndevoltEnergyMode.OUTDOOR_PORTABLE
    )
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Mock call to pause (dis)charging
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_ID_GEN2},
            blocking=True,
        )

    # Verify correct translation key is used for the error and confirm no call was made
    assert (
        exc_info.value.translation_key
        == "energy_mode_change_unavailable_outdoor_portable"
    )
    mock_indevolt.set_data.assert_not_called()
