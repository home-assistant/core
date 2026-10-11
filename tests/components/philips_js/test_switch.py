"""Tests for the Philips TV switches."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from haphilipsjs import PhilipsTV
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.philips_js.const import TV_STATE_OFF
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_MENU_CURRENT

from tests.common import MockConfigEntry, snapshot_platform

MENU_SWITCH_ENTITY_ID = "switch.philips_tv_toggle"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the switch platform."""
    with patch("homeassistant.components.philips_js.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    ("entity_id", "screenstate", "huelamp_power"),
    [
        pytest.param(
            "switch.philips_tv_screen_state",
            TV_STATE_OFF,
            None,
            id="screen",
        ),
        pytest.param(
            "switch.philips_tv_ambilight_hue",
            None,
            TV_STATE_OFF,
            id="ambilight-hue",
        ),
    ],
)
async def test_available_without_powerstate(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    screenstate: str | None,
    huelamp_power: str | None,
) -> None:
    """Test switches are available when the power state endpoint is absent."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.powerstate = None
    mock_tv.screenstate = screenstate
    mock_tv.huelamp_power = huelamp_power

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF


async def test_menu_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_menu_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities with a menu switch."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_menu_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("service", "value"),
    [
        pytest.param(SERVICE_TURN_ON, True, id="turn-on"),
        pytest.param(SERVICE_TURN_OFF, False, id="turn-off"),
    ],
)
async def test_menu_switch_turn_on_off(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    service: str,
    value: bool,
) -> None:
    """Test turning a menu switch on and off."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MENU_SWITCH_ENTITY_ID},
        blocking=True,
    )

    mock_tv.postMenuItemsSettingsUpdateData.assert_called_once_with(
        {2: {"value": value}}
    )


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(
            {"Nodeid": 2, "Controllable": True, "Available": False, "data": {}},
            id="not-available",
        ),
        pytest.param(None, id="not-reported"),
    ],
)
async def test_menu_switch_unavailable(
    hass: HomeAssistant,
    mock_menu_config_entry: MockConfigEntry,
    value: dict[str, Any] | None,
) -> None:
    """Test a menu switch is unavailable when the TV doesn't offer the setting."""
    with patch.dict(MOCK_MENU_CURRENT, {2: value}):
        assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get(MENU_SWITCH_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
