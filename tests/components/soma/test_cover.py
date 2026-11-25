"""Tests for the Soma cover platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from api.soma_api import SomaApi
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverEntityCapabilityAttribute,
    CoverService,
)
from homeassistant.components.soma import DOMAIN
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant

ENTITY_ID = "cover.living_room_blind"
MAC = "aa:bb:cc:dd:ee:ff"


@pytest.fixture
def mock_set_shade_position() -> Generator[MagicMock]:
    """Set up the Soma API with one tilt device and return its position setter."""
    with (
        patch.object(
            SomaApi,
            "list_devices",
            return_value={
                "result": "success",
                "shades": [{"mac": MAC, "name": "Living room blind", "type": "tilt"}],
            },
        ),
        patch.object(
            SomaApi,
            "get_shade_state",
            return_value={"result": "success", "position": 100},
        ),
        patch.object(
            SomaApi, "set_shade_position", return_value={"result": "success"}
        ) as set_shade_position,
        patch("homeassistant.components.soma.PLATFORMS", [Platform.COVER]),
    ):
        yield set_shade_position


async def _setup_integration(hass: HomeAssistant) -> None:
    """Set up the Soma integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4", "port": 3000})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_set_shade_position")
async def test_tilt_positions(hass: HomeAssistant) -> None:
    """Test a tilt device is open in the middle and closed at both ends."""
    await _setup_integration(hass)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[CoverEntityCapabilityAttribute.OPEN_TILT_POSITION] == 50
    assert state.attributes[CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS] == [
        0,
        100,
    ]


@pytest.mark.parametrize(
    ("service", "api_position"),
    [
        pytest.param(CoverService.OPEN_TILT, 0, id="open"),
        pytest.param(CoverService.CLOSE_TILT, 100, id="close"),
    ],
)
async def test_open_and_close_tilt(
    hass: HomeAssistant,
    mock_set_shade_position: MagicMock,
    service: CoverService,
    api_position: int,
) -> None:
    """Test opening the tilt moves the slats to the middle, where they are open."""
    await _setup_integration(hass)

    await hass.services.async_call(
        COVER_DOMAIN, service, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_set_shade_position.assert_called_once_with(MAC, api_position)
