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

DAY_LIGHT_ENTITY_ID = "light.nursery_yoto_day_ambient_light"
NIGHT_LIGHT_ENTITY_ID = "light.nursery_yoto_night_ambient_light"


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


async def test_no_lights_for_mini(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Yoto Mini has no ambient light, so no light entities are created."""
    player = mock_yoto_client.players[PLAYER_ID]
    player.device = replace(player.device, device_family="mini")

    await _setup(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(LIGHT_DOMAIN)


@pytest.mark.parametrize(
    ("entity_id", "service_data", "expected_colour"),
    [
        # Configured day colour #40bfd9 reports brightness 217 (its
        # brightest channel); a new colour is scaled back by it.
        pytest.param(
            DAY_LIGHT_ENTITY_ID,
            {ATTR_RGB_COLOR: (255, 0, 0)},
            {"day_ambient_colour": "#d90000"},
            id="day-set-colour",
        ),
        pytest.param(
            DAY_LIGHT_ENTITY_ID,
            {ATTR_BRIGHTNESS: 128},
            {"day_ambient_colour": "#267080"},
            id="day-set-brightness",
        ),
        pytest.param(
            DAY_LIGHT_ENTITY_ID,
            {ATTR_RGB_COLOR: (0, 255, 0), ATTR_BRIGHTNESS: 255},
            {"day_ambient_colour": "#00ff00"},
            id="day-set-colour-and-brightness",
        ),
        # Night light is off (#000000); turning it on without arguments
        # defaults to white at full brightness.
        pytest.param(
            NIGHT_LIGHT_ENTITY_ID,
            {},
            {"night_ambient_colour": "#ffffff"},
            id="night-turn-on-default",
        ),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    service_data: dict[str, object],
    expected_colour: dict[str, str],
) -> None:
    """Turning on writes the matching ambient colour config field."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, **expected_colour
    )
    mock_yoto_client.update_player_info.assert_awaited_once_with(PLAYER_ID)


async def test_turn_off(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning off writes black to the ambient colour config field."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DAY_LIGHT_ENTITY_ID},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, day_ambient_colour="#000000"
    )


async def test_turn_on_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed config write raises a Home Assistant error."""
    await _setup(hass, mock_config_entry)
    mock_yoto_client.set_player_config.side_effect = YotoError("MQTT timeout")

    with pytest.raises(
        HomeAssistantError, match="Failed to update Yoto player settings"
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DAY_LIGHT_ENTITY_ID},
            blocking=True,
        )
