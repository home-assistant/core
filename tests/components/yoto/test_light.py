"""Tests for the Yoto light platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import YotoError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import PLAYER_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_credentials")

LIGHT_ENTITY_ID = "light.nursery_yoto_ambient_light"


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the integration with only the light platform."""
    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("mock_yoto_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Yoto light entity."""
    await _setup(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_light_for_mini(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Yoto Mini has no ambient light, so no light entity is created."""
    player = mock_yoto_client.players[PLAYER_ID]
    player.device = replace(player.device, device_family="mini")

    await _setup(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(LIGHT_DOMAIN)


@pytest.mark.parametrize(
    ("service_data", "expected_rgb"),
    [
        # The lamp colour is 0x194a55: brightness 85 (its brightest
        # channel), full-brightness colour (75, 222, 255). New values are
        # combined with whichever half the call does not provide.
        pytest.param(
            {ATTR_RGB_COLOR: (255, 0, 0)},
            (85, 0, 0),
            id="set-colour-keeps-brightness",
        ),
        pytest.param(
            {ATTR_BRIGHTNESS: 128},
            (38, 111, 128),
            id="set-brightness-keeps-colour",
        ),
        pytest.param(
            {ATTR_RGB_COLOR: (0, 255, 0), ATTR_BRIGHTNESS: 255},
            (0, 255, 0),
            id="set-colour-and-brightness",
        ),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service_data: dict[str, object],
    expected_rgb: tuple[int, int, int],
) -> None:
    """Turning on sends the combined colour to the player."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_yoto_client.set_ambients.assert_awaited_once_with(PLAYER_ID, *expected_rgb)
    mock_yoto_client.request_player_status.assert_awaited_once_with(PLAYER_ID)


async def test_turn_on_while_off(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning on an unlit lamp without arguments defaults to white."""
    mock_yoto_client.players[PLAYER_ID].status.nightlight_mode = "off"
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )

    mock_yoto_client.set_ambients.assert_awaited_once_with(PLAYER_ID, 255, 255, 255)


async def test_turn_off(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning off sends black to the player."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )

    mock_yoto_client.set_ambients.assert_awaited_once_with(PLAYER_ID, 0, 0, 0)


async def test_turn_on_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed lamp command raises a Home Assistant error."""
    await _setup(hass, mock_config_entry)
    mock_yoto_client.set_ambients.side_effect = YotoError("MQTT timeout")

    with pytest.raises(HomeAssistantError, match="Yoto command failed"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
            blocking=True,
        )
