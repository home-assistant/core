"""Tests for the Sonos number platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CROSSOVER_ENTITY = "number.zone_a_sub_crossover_frequency"


@pytest.fixture(name="platform_select", autouse=True)
async def platform_binary_sensor_fixture():
    """Patch Sonos to only load select platform."""
    with patch("homeassistant.components.sonos.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.parametrize(
    ("level", "result"),
    [
        (0, "off"),
        (1, "low"),
        (2, "medium"),
        (3, "high"),
        (4, "max"),
    ],
)
async def test_select_dialog_level(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
    entity_registry: er.EntityRegistry,
    speaker_info: dict[str, str],
    level: int,
    result: str,
) -> None:
    """Test number entities."""

    speaker_info["model_name"] = "Sonos Arc Ultra"
    soco.get_speaker_info.return_value = speaker_info
    soco.dialog_level = level

    await async_setup_sonos()

    dialog_level_select = entity_registry.entities["select.zone_a_dialog_level"]
    dialog_level_state = hass.states.get(dialog_level_select.entity_id)
    assert dialog_level_state.state == result


@pytest.mark.parametrize(
    ("result", "option"),
    [
        (0, "off"),
        (1, "low"),
        (2, "medium"),
        (3, "high"),
        (4, "max"),
    ],
)
async def test_select_dialog_level_set(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
    entity_registry: er.EntityRegistry,
    speaker_info: dict[str, str],
    result: int,
    option: str,
) -> None:
    """Test number entities."""

    speaker_info["model_name"] = "Sonos Arc Ultra"
    soco.get_speaker_info.return_value = speaker_info
    soco.dialog_level = 0

    await async_setup_sonos()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.zone_a_dialog_level", ATTR_OPTION: option},
        blocking=True,
    )

    assert soco.dialog_level == result
