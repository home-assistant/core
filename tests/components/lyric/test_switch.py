"""Tests for the Honeywell Lyric switch platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import ANY, MagicMock, patch

from aiolyric.exceptions import LyricException
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "switch.hallway_thermostat_emergency_heat"
LCC_MAC_ID = "AABBCC000011"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the switch platform."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.fixture
async def mock_lyric(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_config_entry: MockConfigEntry,
    mock_lyric_thermostats: MagicMock,
) -> MagicMock:
    """Set up the integration and return the mocked Lyric client."""
    await setup_integration(hass, mock_config_entry)
    return mock_lyric_thermostats


@pytest.mark.usefixtures("mock_lyric")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test only thermostats that allow emergency heat get a switch."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def _async_set_mode(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    freezer: FrozenDateTimeFactory,
    mode: str,
) -> None:
    """Set the thermostat mode and refresh the coordinator."""
    device = mock_lyric.locations[0].devices_dict[LCC_MAC_ID]
    device.attributes["changeableValues"]["mode"] = mode
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_switch_on(
    hass: HomeAssistant, mock_lyric: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the switch is on while the thermostat is in emergency heat."""
    await _async_set_mode(hass, mock_lyric, freezer, "EmergencyHeat")

    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    ("current_mode", "service", "mode"),
    [
        pytest.param("Heat", SERVICE_TURN_ON, "EmergencyHeat", id="turn_on"),
        pytest.param("EmergencyHeat", SERVICE_TURN_OFF, "Heat", id="turn_off"),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    freezer: FrozenDateTimeFactory,
    current_mode: str,
    service: str,
    mode: str,
) -> None:
    """Test turning emergency heat on and off."""
    await _async_set_mode(hass, mock_lyric, freezer, current_mode)
    mock_lyric.get_locations.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(ANY, ANY, mode=mode)
    mock_lyric.get_locations.assert_awaited_once()


@pytest.mark.parametrize("current_mode", ["Off", "Heat", "Cool", "Auto"])
async def test_turn_off_keeps_other_modes(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    freezer: FrozenDateTimeFactory,
    current_mode: str,
) -> None:
    """Test turning the switch off when emergency heat is off leaves the mode alone."""
    await _async_set_mode(hass, mock_lyric, freezer, current_mode)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_lyric.update_thermostat.assert_not_awaited()


async def test_turn_on_error(hass: HomeAssistant, mock_lyric: MagicMock) -> None:
    """Test API errors are raised as translated errors and data is still refreshed."""
    mock_lyric.update_thermostat.side_effect = LyricException("error")
    mock_lyric.get_locations.reset_mock()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert err.value.translation_key == "failed_to_set_emergency_heat"
    mock_lyric.get_locations.assert_awaited_once()
