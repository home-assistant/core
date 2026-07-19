"""Tests for LG webOS TV switch platform."""

from unittest.mock import AsyncMock

from aiowebostv import WebOsTvCommandError
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_webostv
from .const import FAKE_UUID

SWITCH_ENTITY_ID = f"{SWITCH_DOMAIN}.lg_webos_tv_model_screen"


async def fire_state_update(client: AsyncMock) -> None:
    """Trigger all registered state update callbacks."""
    for call in client.register_state_update_callback.call_args_list:
        await call[0][0](client.tv_state)


async def test_screen_switch_setup(
    hass: HomeAssistant,
    client: AsyncMock,
) -> None:
    """Test setup of LG webOS TV screen switch."""
    await setup_webostv(hass)

    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get(SWITCH_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{FAKE_UUID}_screen"

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_screen_switch_state_updates(
    hass: HomeAssistant,
    client: AsyncMock,
) -> None:
    """Test screen switch state updates from client."""
    await setup_webostv(hass)

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    client.tv_state.is_screen_on = True
    await fire_state_update(client)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    client.tv_state.is_on = False
    client.tv_state.is_screen_on = False
    await fire_state_update(client)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_screen_switch_turn_on(
    hass: HomeAssistant,
    client: AsyncMock,
) -> None:
    """Test turning on the screen switch."""
    await setup_webostv(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )

    client.request.assert_called_once_with(
        "com.webos.service.tvpower/power/turnOnScreen"
    )


async def test_screen_switch_turn_off(
    hass: HomeAssistant,
    client: AsyncMock,
) -> None:
    """Test turning off the screen switch."""
    await setup_webostv(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )

    client.request.assert_called_once_with(
        "com.webos.service.tvpower/power/turnOffScreen"
    )


async def test_screen_switch_command_error(
    hass: HomeAssistant,
    client: AsyncMock,
) -> None:
    """Test error handling when turning on screen fails."""
    await setup_webostv(hass)
    client.request.side_effect = WebOsTvCommandError("Communication error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )
