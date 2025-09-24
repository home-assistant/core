"""Tests for analytics platform."""

import pytest

from homeassistant.components.analytics import async_devices_payload
from homeassistant.components.onkyo import DOMAIN
from homeassistant.components.onkyo.const import (
    OPTION_INPUT_SOURCES,
    OPTION_LISTENING_MODES,
    InputSource,
    ListeningMode,
)
from homeassistant.components.onkyo.util import get_meaning
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_analytics(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the analytics platform."""
    await async_setup_component(hass, "analytics", {})

    mock_config_entry = MockConfigEntry(
        domain="onkyo",
        options={
            OPTION_INPUT_SOURCES: {
                InputSource("01").value: "Apple TV",
                InputSource("10").value: "Cinema",
            },
            OPTION_LISTENING_MODES: {
                ListeningMode("00").value: "Stereo",
                ListeningMode("80").value: "Dolby Atmos",
            },
        },
    )
    mock_config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        domain=Platform.MEDIA_PLAYER,
        platform="onkyo",
        unique_id="media_player1",
        suggested_object_id="my_media_player",
        capabilities={
            "source_list": ["Apple TV", "Cinema"],
            "sound_mode_list": ["Stereo", "Dolby Atmos"],
        },
        config_entry=mock_config_entry,
    )
    entity_registry.async_get_or_create(
        domain=Platform.MEDIA_PLAYER,
        platform="onkyo",
        unique_id="media_player2",
        suggested_object_id="my_media_player2",
        capabilities={},
        config_entry=mock_config_entry,
    )
    entity_registry.async_get_or_create(
        domain=Platform.SELECT,
        platform="onkyo",
        unique_id="select1",
        suggested_object_id="my_select",
        capabilities={"options": ["a", "b", "c"]},
        config_entry=mock_config_entry,
    )

    result = await async_devices_payload(hass)
    assert result["integrations"][DOMAIN]["entities"] == [
        {
            "assumed_state": None,
            "capabilities": {
                "source_list": [
                    get_meaning(InputSource("01")),
                    get_meaning(InputSource("10")),
                ],
                "sound_mode_list": [
                    get_meaning(ListeningMode("00")),
                    get_meaning(ListeningMode("80")),
                ],
            },
            "domain": "media_player",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": [
                "capabilities",
            ],
            "original_device_class": None,
            "unit_of_measurement": None,
        },
        {
            "assumed_state": None,
            "capabilities": {},
            "domain": "media_player",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": None,
            "original_device_class": None,
            "unit_of_measurement": None,
        },
        {
            "assumed_state": None,
            "capabilities": {
                "options": ["a", "b", "c"],
            },
            "domain": "select",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": None,
            "original_device_class": None,
            "unit_of_measurement": None,
        },
    ]
