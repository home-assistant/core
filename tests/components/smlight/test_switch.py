"""Tests for the SMLIGHT switch platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmlight import Sensors
from pysmlight.const import Settings
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import SCAN_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.SWITCH]


async def test_switch_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of SMLIGHT switches."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("entity", "setting", "field"),
    [
        ("disable_leds", Settings.DISABLE_LEDS, "disable_leds"),
        ("led_night_mode", Settings.NIGHT_MODE, "night_mode"),
        ("auto_zigbee_update", Settings.ZB_AUTOUPDATE, "auto_zigbee"),
    ],
)
async def test_switches(
    hass: HomeAssistant,
    entity: str,
    field: str,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    setting: Settings,
) -> None:
    """Test the SMLIGHT switches."""
    await setup_integration(hass, mock_config_entry)

    _page, _toggle = setting.value

    entity_id = f"switch.mock_title_{entity}"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_smlight_client.set_toggle.mock_calls) == 1
    mock_smlight_client.set_toggle.assert_called_once_with(_page, _toggle, True)
    mock_smlight_client.get_sensors.return_value = Sensors(**{field: True})

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_smlight_client.set_toggle.mock_calls) == 2
    mock_smlight_client.set_toggle.assert_called_with(_page, _toggle, False)
    mock_smlight_client.get_sensors.return_value = Sensors(**{field: False})

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
