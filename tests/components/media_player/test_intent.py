"""Tests for the media_player intents."""
from homeassistant.components import media_player
from homeassistant.components.media_player import intent
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.intent import async_handle

from tests.common import async_mock_service


async def test_intent_volume_up(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the volume up intent."""

    entry = entity_registry.async_get_or_create(media_player.DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_ON)
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_UP
    )

    await intent.async_setup_intents(hass)

    response = await async_handle(
        hass,
        "test",
        intent.INTENT_VOLUME_UP,
    )

    # Response should contain one target
    assert len(response.success_results) == 1
    assert len(calls) == 1


async def test_intent_volume_down(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the volume up intent."""

    entry = entity_registry.async_get_or_create(media_player.DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_ON)
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_DOWN
    )

    await intent.async_setup_intents(hass)

    response = await async_handle(
        hass,
        "test",
        intent.INTENT_VOLUME_DOWN,
    )

    # Response should contain one target
    assert len(response.success_results) == 1
    assert len(calls) == 1
