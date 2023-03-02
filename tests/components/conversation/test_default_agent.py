"""Test for the default agent."""
import pytest

from homeassistant.components import conversation
from homeassistant.core import DOMAIN as HASS_DOMAIN, Context
from homeassistant.helpers import entity, entity_registry, intent
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
async def test_hidden_entities_skipped(hass, init_components, er_kwargs):
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
