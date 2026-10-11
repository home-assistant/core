"""Tests for the Philips TV coordinator."""

from collections.abc import Callable
from copy import deepcopy
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from haphilipsjs import AutenticationFailure, ConnectionFailure, GeneralFailure
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import (
    MOCK_MENU_CURRENT,
    MOCK_MENU_DATA,
    MOCK_MENU_ROOT,
    MOCK_MENU_STORAGE_KEY,
    MOCK_MENU_STRINGS,
)

from tests.common import MockConfigEntry, async_fire_time_changed

MENU_SWITCH_ENTITY_ID = "switch.philips_tv_toggle"
SCREEN_SWITCH_ENTITY_ID = "switch.philips_tv_screen_state"
NEW_STRING_ID = "org.droidtv.ui.strings.R.string.MAIN_NEW"


def _rename_node(index: int) -> dict[str, Any]:
    """Return the menu structure with a new string id for a child of the root."""
    root = deepcopy(MOCK_MENU_ROOT)
    root["data"]["nodes"][index]["string_id"] = NEW_STRING_ID
    return root


async def test_menu_stored(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_menu_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the menu is read from the TV and stored."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass_storage[MOCK_MENU_STORAGE_KEY]["data"] == MOCK_MENU_DATA
    assert "Selected menu settings [99] are no longer provided by the TV" in caplog.text


async def test_menu_loaded_from_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
) -> None:
    """Test menu entities are created from the stored menu while the TV is off."""
    hass_storage[MOCK_MENU_STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": MOCK_MENU_STORAGE_KEY,
        "data": MOCK_MENU_DATA,
    }
    mock_tv.update.return_value = False
    mock_tv.settings = None

    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
    mock_tv.getStringsCached.assert_not_called()


@pytest.mark.parametrize(
    ("structure", "reloads"),
    [
        pytest.param(lambda: deepcopy(MOCK_MENU_ROOT), 0, id="unchanged"),
        # Sound style node 9 is not selected
        pytest.param(lambda: _rename_node(7), 0, id="unselected-node-renamed"),
        # Toggle node 2 is selected
        pytest.param(lambda: _rename_node(0), 1, id="selected-node-renamed"),
    ],
)
async def test_menu_changed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    structure: Callable[[], dict[str, Any]],
    reloads: int,
) -> None:
    """Test the entry is reloaded when a new menu changes the selected nodes."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    # The api replaces the settings object when the TV turns on again
    mock_tv.settings = {"node": structure()}
    with (
        patch.dict(MOCK_MENU_STRINGS, {NEW_STRING_ID: "New"}),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert mock_reload.call_count == reloads
    assert hass_storage[MOCK_MENU_STORAGE_KEY]["data"]["structure"] == structure()


@pytest.mark.parametrize(
    "post_config",
    [
        pytest.param({"side_effect": GeneralFailure("")}, id="exception"),
        pytest.param({"return_value": None}, id="failed-request"),
    ],
)
async def test_update_menu_setting_failed(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    post_config: dict[str, Any],
) -> None:
    """Test a failed write of a menu setting."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_tv.postMenuItemsSettingsUpdateData.configure_mock(**post_config)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: MENU_SWITCH_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_key == "update_failed"


async def test_update_menu_setting_read_back(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
) -> None:
    """Test the settings are read back after a write."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    off = deepcopy(MOCK_MENU_CURRENT[2])
    off["data"]["value"] = False
    with patch.dict(MOCK_MENU_CURRENT, {2: off}):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: MENU_SWITCH_ENTITY_ID},
            blocking=True,
        )

    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_OFF


async def test_update_menu_setting_read_back_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
) -> None:
    """Test a full refresh is requested when reading back after a write fails."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = ConnectionFailure("")
    mock_tv.update.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MENU_SWITCH_ENTITY_ID},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_tv.update.assert_called_once()


async def test_notify_settings_changed(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
) -> None:
    """Test settings are read when the TV notifies a new settings version."""
    mock_tv.powerstate = "On"
    mock_tv.notify_change_supported = True
    off = deepcopy(MOCK_MENU_CURRENT[2])
    off["data"]["value"] = False

    # A change is notified once, then None stops the notify loop
    results = iter([True, None])

    def _notify_change(timeout: int) -> bool | None:
        mock_tv.settings_version = 1
        MOCK_MENU_CURRENT[2] = off
        return next(results)

    mock_tv.notifyChange.side_effect = _notify_change
    with patch.dict(MOCK_MENU_CURRENT):
        assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_tv.notifyChange.call_count == 2
    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ConnectionFailure(""), id="connection-failure"),
        pytest.param(GeneralFailure(""), id="general-failure"),
    ],
)
async def test_notify_settings_update_failed(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
) -> None:
    """Test the notify loop stops when reading changed settings fails."""
    caplog.set_level(logging.DEBUG)
    mock_tv.powerstate = "On"
    mock_tv.notify_change_supported = True

    def _notify_change(timeout: int) -> bool:
        mock_tv.settings_version = 1
        mock_tv.getMenuItemsSettingsCurrentValue.side_effect = exception
        return True

    mock_tv.notifyChange.side_effect = _notify_change
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_tv.notifyChange.call_count == 1
    assert "Aborting notify due to failed settings update" in caplog.text
    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ConnectionFailure(""), id="connection-failure"),
        pytest.param(GeneralFailure(""), id="general-failure"),
    ],
)
async def test_settings_read_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    exception: Exception,
) -> None:
    """Test only menu entities are unavailable when reading settings fails."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_ON

    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = exception
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(SCREEN_SWITCH_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        pytest.param(GeneralFailure(""), ConfigEntryState.LOADED, id="general-failure"),
        pytest.param(
            AutenticationFailure(""),
            ConfigEntryState.SETUP_ERROR,
            id="authentication-failure",
        ),
    ],
)
async def test_setup_menu_read_failed(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test a failed menu read only fails setup for authentication failures."""
    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = exception

    await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_menu_config_entry.state is entry_state
