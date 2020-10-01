"""Test the Advantage Air Cover Platform."""

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DAMPER,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
)
from homeassistant.const import ATTR_ENTITY_ID

from tests.components.advantage_air import add_mock_config, api_response


async def test_cover_async_setup_entry(hass, aiohttp_raw_server, aiohttp_unused_port):
    """Test climate setup without sensors."""

    port = aiohttp_unused_port()
    await aiohttp_raw_server(api_response, port=port)
    await add_mock_config(hass, port)

    registry = await hass.helpers.entity_registry.async_get_registry()

    # Test Cover Zone Entity
    entity_id = "cover.zone_open_without_sensor_vent"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("device_class") == DEVICE_CLASS_DAMPER
    assert state.attributes.get("current_position") == 100

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac2-z01"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 50},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 0},
        blocking=True,
    )
