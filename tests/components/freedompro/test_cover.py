"""Tests for the Freedompro cover."""
from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_SET_COVER_POSITION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED
from homeassistant.helpers import entity_registry as er


async def test_cover_get_state(hass, init_integration):
    """Test states of the cover."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "cover.blind"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED
    assert state.attributes.get("friendly_name") == "blind"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS"
    )


async def test_cover_set_position(hass, init_integration):
    """Test set on of the cover."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "cover.blind"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED
    assert state.attributes.get("friendly_name") == "blind"

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

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED
