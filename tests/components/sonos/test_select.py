"""Tests for the Sonos number platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.sonos.const import ATTR_DIALOG_LEVEL, MODEL_SONOS_ARC_ULTRA
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .conftest import create_rendering_control_event

SELECT_DIALOG_LEVEL_ENTITY = "select.zone_a_dialog_level"


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
    """Test dialog level select entity."""

    speaker_info["model_name"] = MODEL_SONOS_ARC_ULTRA.lower()
    soco.get_speaker_info.return_value = speaker_info
    soco.dialog_level = level

    await async_setup_sonos()

    dialog_level_select = entity_registry.entities[SELECT_DIALOG_LEVEL_ENTITY]
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
    speaker_info: dict[str, str],
    result: int,
    option: str,
) -> None:
    """Test setting dialog level select entity."""

    speaker_info["model_name"] = MODEL_SONOS_ARC_ULTRA.lower()
    soco.get_speaker_info.return_value = speaker_info
    soco.dialog_level = 0

    await async_setup_sonos()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_DIALOG_LEVEL_ENTITY, ATTR_OPTION: option},
        blocking=True,
    )

    assert soco.dialog_level == result


async def test_select_dialog_level_only_arc_ultra(
    hass: HomeAssistant,
    async_setup_sonos,
    entity_registry: er.EntityRegistry,
    speaker_info: dict[str, str],
) -> None:
    """Test the dialog level select is only created for Sonos Arc Ultra."""

    speaker_info["model_name"] = "Sonos S1"
    await async_setup_sonos()

    assert SELECT_DIALOG_LEVEL_ENTITY not in entity_registry.entities


async def test_select_dialog_level_event(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
    entity_registry: er.EntityRegistry,
    speaker_info: dict[str, str],
) -> None:
    """Test dialog level select entity updated by event."""

    speaker_info["model_name"] = MODEL_SONOS_ARC_ULTRA.lower()
    soco.get_speaker_info.return_value = speaker_info
    soco.dialog_level = 0

    await async_setup_sonos()

    event = create_rendering_control_event(soco)
    event.variables[ATTR_DIALOG_LEVEL] = 3
    soco.renderingControl.subscribe.return_value._callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)

    dialog_level_select = entity_registry.entities[SELECT_DIALOG_LEVEL_ENTITY]
    dialog_level_state = hass.states.get(dialog_level_select.entity_id)
    assert dialog_level_state.state == "high"
    pass