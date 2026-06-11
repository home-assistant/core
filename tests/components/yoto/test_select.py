"""Tests for the Yoto select platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import YotoError

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import PLAYER_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_credentials")

DAY_SELECT_ENTITY_ID = "select.nursery_yoto_day_ambient_light_color"
NIGHT_SELECT_ENTITY_ID = "select.nursery_yoto_night_ambient_light_color"


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the integration with only the select platform."""
    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("mock_yoto_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Yoto select entity."""
    await _setup(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_selects_for_mini(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Yoto Mini has no ambient light, so no select entities are created."""
    player = mock_yoto_client.players[PLAYER_ID]
    player.device = replace(player.device, device_family="mini")

    await _setup(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(SELECT_DOMAIN)


@pytest.mark.parametrize(
    ("colour", "expected_state"),
    [
        # The app has written several hex variants per preset over time.
        pytest.param("#41C0F0", "sky_blue", id="alias-hex-case-insensitive"),
        pytest.param("#ffb800", "bumblebee_yellow", id="alias-hex"),
        pytest.param("off", "off", id="off-sentinel"),
        pytest.param("#123456", STATE_UNKNOWN, id="unrecognised-colour"),
        pytest.param(None, STATE_UNKNOWN, id="unset"),
    ],
)
async def test_colour_parsing(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    colour: str | None,
    expected_state: str,
) -> None:
    """Every known colour variant maps to its preset; unknown ones do not."""
    mock_yoto_client.players[PLAYER_ID].info.config.day_ambient_colour = colour
    await _setup(hass, mock_config_entry)

    assert hass.states.get(DAY_SELECT_ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("entity_id", "option", "expected_fields"),
    [
        pytest.param(
            DAY_SELECT_ENTITY_ID,
            "tambourine_red",
            {"day_ambient_colour": "#ff0000"},
            id="day-preset",
        ),
        pytest.param(
            NIGHT_SELECT_ENTITY_ID,
            "white",
            {"night_ambient_colour": "#ffffff"},
            id="night-preset",
        ),
        pytest.param(
            NIGHT_SELECT_ENTITY_ID,
            "off",
            {"night_ambient_colour": "#000000"},
            id="night-off",
        ),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    option: str,
    expected_fields: dict[str, str],
) -> None:
    """Selecting a preset writes its colour to the player config."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, **expected_fields
    )
    mock_yoto_client.update_player_info.assert_awaited_once_with(PLAYER_ID)


async def test_select_option_failure(
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
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: DAY_SELECT_ENTITY_ID, ATTR_OPTION: "white"},
            blocking=True,
        )
