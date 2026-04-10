"""The tests for the vacuum platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.vacuum import (
    DOMAIN,
    SERVICE_CLEAN_AREA,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    VacuumEntityFeature,
    intent as vacuum_intent,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, intent

from tests.common import async_mock_service


async def test_start(hass: HomeAssistant) -> None:
    """Test HassVacuumStart intent."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(
        entity_id, STATE_IDLE, {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.START}
    )
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


async def test_start_without_name(hass: HomeAssistant) -> None:
    """Test HassVacuumStart intent without specifying the name."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(
        entity_id, STATE_IDLE, {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.START}
    )
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


async def test_return_to_base(hass: HomeAssistant) -> None:
    """Test HassVacuumReturnToBase intent."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(
        entity_id,
        STATE_IDLE,
        {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.RETURN_HOME},
    )
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


async def test_return_to_base_without_name(hass: HomeAssistant) -> None:
    """Test HassVacuumReturnToBase intent without specifying the name."""
    await vacuum_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(
        entity_id,
        STATE_IDLE,
        {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.RETURN_HOME},
    )
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


async def test_clean_area(hass: HomeAssistant) -> None:
    """Test HassVacuumCleanArea intent."""
    await vacuum_intent.async_setup_intents(hass)

    area_reg = ar.async_get(hass)
    kitchen = area_reg.async_create("Kitchen")

    vacuum_1 = f"{DOMAIN}.vacuum_1"
    vacuum_2 = f"{DOMAIN}.vacuum_2"
    for entity_id in (vacuum_1, vacuum_2):
        hass.states.async_set(
            entity_id,
            STATE_IDLE,
            {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.CLEAN_AREA},
        )
    calls = async_mock_service(hass, DOMAIN, SERVICE_CLEAN_AREA)

    # Without name: all vacuums receive the service call
    response = await intent.async_handle(
        hass,
        "test",
        vacuum_intent.INTENT_VACUUM_CLEAN_AREA,
        {"area": {"value": "Kitchen"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert set(calls[0].data["entity_id"]) == {vacuum_1, vacuum_2}
    assert calls[0].data["cleaning_area_id"] == [kitchen.id]

    assert len(response.success_results) == 3
    assert response.success_results[0].type == intent.IntentResponseTargetType.AREA
    assert response.success_results[0].id == kitchen.id
    assert all(
        t.type == intent.IntentResponseTargetType.ENTITY
        for t in response.success_results[1:]
    )
    assert {t.id for t in response.success_results[1:]} == {vacuum_1, vacuum_2}

    # With name: only the named vacuum receives the call
    calls.clear()
    response = await intent.async_handle(
        hass,
        "test",
        vacuum_intent.INTENT_VACUUM_CLEAN_AREA,
        {"name": {"value": "vacuum 1"}, "area": {"value": "Kitchen"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": [vacuum_1],
        "cleaning_area_id": [kitchen.id],
    }


async def test_clean_area_no_matching_vacuum(hass: HomeAssistant) -> None:
    """Test HassVacuumCleanArea intent with no matching vacuum."""
    await vacuum_intent.async_setup_intents(hass)

    area_reg = ar.async_get(hass)
    area_reg.async_create("Kitchen")

    # No vacuums at all
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            vacuum_intent.INTENT_VACUUM_CLEAN_AREA,
            {"area": {"value": "Kitchen"}},
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.DOMAIN

    # Vacuum without CLEAN_AREA feature
    hass.states.async_set(
        f"{DOMAIN}.test_vacuum",
        STATE_IDLE,
        {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.START},
    )

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            vacuum_intent.INTENT_VACUUM_CLEAN_AREA,
            {"area": {"value": "Kitchen"}},
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.FEATURE


async def test_clean_area_invalid_area(hass: HomeAssistant) -> None:
    """Test HassVacuumCleanArea intent with an invalid area."""
    await vacuum_intent.async_setup_intents(hass)

    hass.states.async_set(
        f"{DOMAIN}.test_vacuum",
        STATE_IDLE,
        {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.CLEAN_AREA},
    )

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            vacuum_intent.INTENT_VACUUM_CLEAN_AREA,
            {"area": {"value": "Nonexistent room"}},
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.INVALID_AREA
    assert err.value.result.no_match_name == "Nonexistent room"


async def test_clean_area_service_failure(hass: HomeAssistant) -> None:
    """Test HassVacuumCleanArea intent when the service call fails."""
    await vacuum_intent.async_setup_intents(hass)

    area_reg = ar.async_get(hass)
    area_reg.async_create("Kitchen")

    entity_id = f"{DOMAIN}.test_vacuum"
    hass.states.async_set(
        entity_id,
        STATE_IDLE,
        {ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.CLEAN_AREA},
    )

    kitchen = area_reg.async_get_area_by_name("Kitchen")
    assert kitchen is not None

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            side_effect=RuntimeError("Service failed"),
        ),
        pytest.raises(intent.IntentHandleError) as err,
    ):
        await intent.async_handle(
            hass,
            "test",
            vacuum_intent.INTENT_VACUUM_CLEAN_AREA,
            {"area": {"value": "Kitchen"}},
        )

    assert str(err.value) == (
        f"Failed to call {SERVICE_CLEAN_AREA} for areas: ['{kitchen.id}']"
        f" with vacuums: ['{entity_id}']"
    )
