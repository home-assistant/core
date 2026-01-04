"""Tests for the BSB-Lan button platform."""

from unittest.mock import MagicMock

from bsblan import BSBLANError, DeviceTime
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_SYNC_TIME = "button.bsb_lan_sync_time"


async def test_button_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the button entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.BUTTON])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_press_syncs_time(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test pressing the sync time button syncs the device time."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.BUTTON])

    # Mock device time that differs from HA time
    mock_bsblan.time.return_value = DeviceTime.from_json(
        '{"time": {"name": "Time", "value": "01.01.2020 00:00:00", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}'
    )

    # Press the button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_SYNC_TIME},
        blocking=True,
    )

    # Verify time() was called to check current device time
    assert mock_bsblan.time.called

    # Verify set_time() was called with current HA time
    current_time_str = dt_util.now().strftime("%d.%m.%Y %H:%M:%S")
    mock_bsblan.set_time.assert_called_once_with(current_time_str)


async def test_button_press_no_update_when_same(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test button press doesn't update when time matches."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.BUTTON])

    # Mock device time that matches HA time
    current_time_str = dt_util.now().strftime("%d.%m.%Y %H:%M:%S")
    mock_bsblan.time.return_value = DeviceTime.from_json(
        f'{{"time": {{"name": "Time", "value": "{current_time_str}", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}}}'
    )

    # Press the button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_SYNC_TIME},
        blocking=True,
    )

    # Verify time() was called
    assert mock_bsblan.time.called

    # Verify set_time() was NOT called since times match
    assert not mock_bsblan.set_time.called


async def test_button_press_error_handling(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button press handles errors gracefully."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.BUTTON])

    # Mock time() to raise an error
    mock_bsblan.time.side_effect = BSBLANError("Connection failed")

    # Press the button - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to sync time"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_SYNC_TIME},
            blocking=True,
        )


async def test_button_press_set_time_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button press handles set_time errors."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.BUTTON])

    # Mock device time that differs
    mock_bsblan.time.return_value = DeviceTime.from_json(
        '{"time": {"name": "Time", "value": "01.01.2020 00:00:00", "unit": "", "desc": "", "dataType": 0, "readonly": 0, "error": 0}}'
    )

    # Mock set_time() to raise an error
    mock_bsblan.set_time.side_effect = BSBLANError("Write failed")

    # Press the button - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to sync time"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_SYNC_TIME},
            blocking=True,
        )
