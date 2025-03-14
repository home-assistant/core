"""The tests for the vacuum platform."""

from homeassistant.components.vacuum import (
    DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    intent as vacuum_intent,
)
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_start_vacuum_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOn intent for vacuums."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_START)

    response = await intent.async_handle(
        hass,
        "test",
        vacuum_intent.INTENT_VACUUM_START,
        {"name": {"value": "test vacuum"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_START
    assert call.data == {"entity_id": entity_id}


async def test_start_vacuum_without_name(hass: HomeAssistant) -> None:
    """Test starting a vacuum without specifying the name."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_START)

    response = await intent.async_handle(
        hass, "test", vacuum_intent.INTENT_VACUUM_START, {}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_START
    assert call.data == {"entity_id": entity_id}


async def test_stop_vacuum_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOff intent for vacuums."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_RETURN_TO_BASE)

    response = await intent.async_handle(
        hass,
        "test",
        vacuum_intent.INTENT_VACUUM_RETURN_TO_BASE,
        {"name": {"value": "test vacuum"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_RETURN_TO_BASE
    assert call.data == {"entity_id": entity_id}


async def test_stop_vacuum_without_name(hass: HomeAssistant) -> None:
    """Test stopping a vacuum without specifying the name."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_RETURN_TO_BASE)

    response = await intent.async_handle(
        hass, "test", vacuum_intent.INTENT_VACUUM_RETURN_TO_BASE, {}
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_RETURN_TO_BASE
    assert call.data == {"entity_id": entity_id}
