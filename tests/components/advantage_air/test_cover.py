"""Test the Advantage Air Cover Platform."""

from unittest.mock import AsyncMock

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    CoverDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config


async def test_ac_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test cover platform."""

    await add_mock_config(hass)

    # Test Cover Zone Entity
    entity_id = "cover.myauto_zone_y"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("device_class") == CoverDeviceClass.DAMPER
    assert state.attributes.get("current_position") == 100

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac3-z01"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 50},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 0},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    # Test controlling multiple Cover Zone Entity
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {
            ATTR_ENTITY_ID: [
                "cover.myauto_zone_y",
                "cover.myauto_zone_z",
            ]
        },
        blocking=True,
    )
    assert len(mock_update.mock_calls) == 2
    mock_update.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            ATTR_ENTITY_ID: [
                "cover.myauto_zone_y",
                "cover.myauto_zone_z",
            ]
        },
        blocking=True,
    )

    assert len(mock_update.mock_calls) == 2


async def test_things_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test cover platform."""

    await add_mock_config(hass)

    # Test Blind 1 Entity
    entity_id = "cover.blind_1"
    thing_id = "200"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("device_class") == CoverDeviceClass.BLIND

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"uniqueid-{thing_id}"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
