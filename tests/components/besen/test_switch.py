"""Tests for the Besen switch platform."""

from unittest.mock import AsyncMock

from besen.exceptions import CommandFailed
import pytest

from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    FIXTURE_ADDRESS,
    BesenClientFixture,
    charger_state,
    setup_with_selected_platforms,
)

from tests.common import MockConfigEntry

ENTITY_ID = "switch.garage_charge"


async def test_switch_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test switch entity state and registry data."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    state = hass.states.get(ENTITY_ID)
    entity_entry = entity_registry.async_get(ENTITY_ID)
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, FIXTURE_ADDRESS)}
    )

    assert state is not None
    assert state.state == STATE_ON
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{FIXTURE_ADDRESS}_charging"
    assert device_entry is not None
    assert device_entry.name == "Garage"
    mock_besen_client.client.async_start.assert_awaited_once()


async def test_switch_updates_from_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test switch state updates from client push data."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    mock_besen_client.publish_state(charger_state(charger_status=False))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_updates_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test switch state updates when the coordinator refreshes."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    mock_besen_client.client.state = charger_state(charger_status=False)
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test switch turn on and turn off services."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    mock_besen_client.client.async_stop_charging.assert_awaited_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    mock_besen_client.client.async_start_charging.assert_awaited_once()


async def test_switch_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: BesenClientFixture,
) -> None:
    """Test command failures are translated to Home Assistant errors."""

    mock_besen_client.client.async_start_charging = AsyncMock(
        side_effect=CommandFailed("failed")
    )

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
