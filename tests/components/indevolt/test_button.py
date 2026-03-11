"""Tests for the Indevolt button platform."""

from unittest.mock import AsyncMock, call, patch

from indevolt_api import TimeOutException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.indevolt.const import (
    ENERGY_MODE_READ_KEY,
    ENERGY_MODE_WRITE_KEY,
    PORTABLE_MODE,
    REALTIME_ACTION_KEY,
    REALTIME_ACTION_MODE,
)
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

    # Verify set_data was called twice with correct parameters
    assert mock_indevolt.set_data.call_count == 2
    mock_indevolt.set_data.assert_has_calls(
        [
            call(ENERGY_MODE_WRITE_KEY, REALTIME_ACTION_MODE),
            call(REALTIME_ACTION_KEY, [0, 0, 0]),
        ]
    )


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_button_press_standby_already_in_realtime_mode(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing standby when already in real-time mode skips the mode switch."""

    # Force real-time control mode
    mock_indevolt.fetch_data.return_value[ENERGY_MODE_READ_KEY] = REALTIME_ACTION_MODE
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

    # Verify set_data was called once with correct parameters
    mock_indevolt.set_data.assert_called_once_with(REALTIME_ACTION_KEY, [0, 0, 0])


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_button_press_standby_timeout_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing standby raises HomeAssistantError when the device times out."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    # Simulate an API push failure
    mock_indevolt.set_data.side_effect = TimeOutException("Timed out")

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
    mock_indevolt.fetch_data.return_value[ENERGY_MODE_READ_KEY] = PORTABLE_MODE
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
