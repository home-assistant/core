"""Test the Advantage Air Switch Platform."""

from unittest.mock import AsyncMock

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import STATE_OFF, STATE_ON, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config


async def test_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test light setup."""

    await add_mock_config(hass)

    # Test Light Entity
    entity_id = "light.light_a"
    light_id = "100"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"uniqueid-{light_id}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: [entity_id]},
        blocking=True,
    )

    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    # Test Dimmable Light Entity
    entity_id = "light.light_b"
    light_id = "101"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"uniqueid-{light_id}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: [entity_id], LightServiceArgument.BRIGHTNESS: 128},
        blocking=True,
    )
    mock_update.assert_called_once()


async def test_things_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test things lights."""

    await add_mock_config(hass)

    # Test Switch Entity
    entity_id = "light.thing_light_dimmable"
    light_id = "204"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"uniqueid-{light_id}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: [entity_id]},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: [entity_id], LightServiceArgument.BRIGHTNESS: 128},
        blocking=True,
    )
    mock_update.assert_called_once()
