"""Tests for the Freedompro cover."""
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_SET_COVER_POSITION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.freedompro import init_integration


async def test_cover_get_state(hass):
    """Test states of the cover."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    entity_id = "cover.bedroom_window_covering"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED
    assert state.attributes.get("friendly_name") == "Bedroom window covering"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS"
    )


async def test_cover_set_position(hass: HomeAssistantType):
    """Test set position of the cover."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    entity_id = "cover.bedroom_window_covering"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED
    assert state.attributes.get("friendly_name") == "Bedroom window covering"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS"
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 33},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 33
