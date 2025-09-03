"""The tests for the lawn mower platform."""

from homeassistant.components.lawn_mower import (
    DOMAIN,
    SERVICE_DOCK,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntityFeature,
    intent as lawn_mower_intent,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_start_lawn_mower_intent(hass: HomeAssistant) -> None:
    """Test HassLawnMowerStartMowing intent for lawn mowers."""
    await lawn_mower_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_lawn_mower"
    hass.states.async_set(
        entity_id,
        LawnMowerActivity.DOCKED,
        {ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.START_MOWING},
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_START_MOWING)

    response = await intent.async_handle(
        hass,
        "test",
        lawn_mower_intent.INTENT_LANW_MOWER_START_MOWING,
        {"name": {"value": "test lawn mower"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_START_MOWING
    assert call.data == {"entity_id": entity_id}


async def test_start_lawn_mower_without_name(hass: HomeAssistant) -> None:
    """Test starting a lawn mower without specifying the name."""
    await lawn_mower_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_lawn_mower"
    hass.states.async_set(
        entity_id,
        LawnMowerActivity.DOCKED,
        {ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.START_MOWING},
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_START_MOWING)

    response = await intent.async_handle(
        hass, "test", lawn_mower_intent.INTENT_LANW_MOWER_START_MOWING, {}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_START_MOWING
    assert call.data == {"entity_id": entity_id}


async def test_stop_lawn_mower_intent(hass: HomeAssistant) -> None:
    """Test HassLawnMowerDock intent for lawn mowers."""
    await lawn_mower_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_lawn_mower"
    hass.states.async_set(
        entity_id,
        LawnMowerActivity.MOWING,
        {ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.DOCK},
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_DOCK)

    response = await intent.async_handle(
        hass,
        "test",
        lawn_mower_intent.INTENT_LANW_MOWER_DOCK,
        {"name": {"value": "test lawn mower"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_DOCK
    assert call.data == {"entity_id": entity_id}


async def test_stop_lawn_mower_without_name(hass: HomeAssistant) -> None:
    """Test stopping a lawn mower without specifying the name."""
    await lawn_mower_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_lawn_mower"
    hass.states.async_set(
        entity_id,
        LawnMowerActivity.MOWING,
        {ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.DOCK},
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_DOCK)

    response = await intent.async_handle(
        hass, "test", lawn_mower_intent.INTENT_LANW_MOWER_DOCK, {}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_DOCK
    assert call.data == {"entity_id": entity_id}
