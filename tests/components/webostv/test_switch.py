"""Tests for LG webOS TV switch platform."""

from unittest.mock import AsyncMock

from aiowebostv import WebOsTvCommandError, WebOsTvServiceNotFoundError
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.webostv.const import DOMAIN
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


async def _async_setup_and_enable_switch(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Set up webostv and enable the screen switch, disabled by default."""
    await setup_webostv(hass)
    entity_registry.async_update_entity(SWITCH_ENTITY_ID, disabled_by=None)
    await hass.async_block_till_done()
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_screen_switch_setup(
    hass: HomeAssistant,
    client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LG webOS TV screen switch is registered but disabled."""
    await setup_webostv(hass)

    entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{FAKE_UUID}_screen"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert hass.states.get(SWITCH_ENTITY_ID) is None


async def test_screen_switch_state_updates(
    hass: HomeAssistant,
    client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test screen switch state updates from client."""
    await _async_setup_and_enable_switch(hass, entity_registry)

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    client.tv_state.is_screen_on = True
    await client.mock_state_update()
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    client.tv_state.is_on = False
    client.tv_state.is_screen_on = False
    await client.mock_state_update()
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("service", "screen_state"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_screen_switch_commands(
    hass: HomeAssistant,
    client: AsyncMock,
    entity_registry: er.EntityRegistry,
    service: str,
    screen_state: bool,
) -> None:
    """Test the screen switch sets the screen state."""
    await _async_setup_and_enable_switch(hass, entity_registry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )

    client.set_screen_state.assert_called_once_with(screen_state)


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_screen_switch_command_error(
    hass: HomeAssistant,
    client: AsyncMock,
    entity_registry: er.EntityRegistry,
    service: str,
) -> None:
    """Test a failing screen command raises a translated error."""
    await _async_setup_and_enable_switch(hass, entity_registry)
    client.set_screen_state.side_effect = WebOsTvCommandError("Communication error")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "communication_error"


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_screen_switch_not_supported(
    hass: HomeAssistant,
    client: AsyncMock,
    entity_registry: er.EntityRegistry,
    service: str,
) -> None:
    """Test a TV without screen control raises a translated error."""
    await _async_setup_and_enable_switch(hass, entity_registry)
    client.set_screen_state.side_effect = WebOsTvServiceNotFoundError(
        "404 no such service or method"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "screen_control_not_supported"

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
