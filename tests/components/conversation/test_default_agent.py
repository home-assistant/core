"""Test for the default agent."""
from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import DOMAIN as HASS_DOMAIN, Context, HomeAssistant
from homeassistant.helpers import (
    area_registry,
    device_registry,
    entity,
    entity_registry,
    intent,
)
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


@pytest.mark.parametrize(
    "er_kwargs",
    [
        {"hidden_by": entity_registry.RegistryEntryHider.USER},
        {"hidden_by": entity_registry.RegistryEntryHider.INTEGRATION},
        {"entity_category": entity.EntityCategory.CONFIG},
        {"entity_category": entity.EntityCategory.DIAGNOSTIC},
    ],
)
async def test_hidden_entities_skipped(
    hass: HomeAssistant, init_components, er_kwargs
) -> None:
    """Test we skip hidden entities."""

    er = entity_registry.async_get(hass)
    er.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="Test light", **er_kwargs
    )
    hass.states.async_set("light.test_light", "off")
    calls = async_mock_service(hass, HASS_DOMAIN, "turn_on")
    result = await conversation.async_converse(
        hass, "turn on test light", None, Context(), None
    )

    assert len(calls) == 0
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH


async def test_exposed_domains(hass: HomeAssistant, init_components) -> None:
    """Test that we can't interact with entities that aren't exposed."""
    hass.states.async_set(
        "media_player.test", "off", attributes={ATTR_FRIENDLY_NAME: "Test Media Player"}
    )

    result = await conversation.async_converse(
        hass, "turn on test media player", None, Context(), None
    )

    # This is an intent match failure instead of a handle failure because the
    # media player domain is not exposed.
    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH


async def test_exposed_areas(hass: HomeAssistant, init_components) -> None:
    """Test that only expose areas with an exposed entity/device."""
    areas = area_registry.async_get(hass)
    area_kitchen = areas.async_get_or_create("kitchen")
    area_bedroom = areas.async_get_or_create("bedroom")

    devices = device_registry.async_get(hass)
    kitchen_device = devices.async_get_or_create(
        config_entry_id="1234", connections=set(), identifiers={("demo", "id-1234")}
    )
    devices.async_update_device(kitchen_device.id, area_id=area_kitchen.id)

    entities = entity_registry.async_get(hass)
    kitchen_light = entities.async_get_or_create("light", "demo", "1234")
    entities.async_update_entity(kitchen_light.entity_id, device_id=kitchen_device.id)
    hass.states.async_set(
        kitchen_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    bedroom_light = entities.async_get_or_create("light", "demo", "5678")
    entities.async_update_entity(bedroom_light.entity_id, area_id=area_bedroom.id)
    hass.states.async_set(
        bedroom_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "bedroom light"}
    )

    def is_entity_exposed(state):
        return state.entity_id != bedroom_light.entity_id

    with patch(
        "homeassistant.components.conversation.default_agent.is_entity_exposed",
        is_entity_exposed,
    ):
        result = await conversation.async_converse(
            hass, "turn on lights in the kitchen", None, Context(), None
        )

        # All is well for the exposed kitchen light
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE

        # Bedroom is not exposed because it has no exposed entities
        result = await conversation.async_converse(
            hass, "turn on lights in the bedroom", None, Context(), None
        )

        # This should be an intent match failure because the area isn't in the slot list
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH
        )
