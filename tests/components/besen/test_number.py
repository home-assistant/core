"""Tests for the Besen number platform."""

from unittest.mock import AsyncMock, Mock

from besen.const import FALLBACK_MAX_CHARGE_AMPS
from besen.exceptions import CommandFailed
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.besen.const import DOMAIN
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import publish_besen_state
from .conftest import charger_state, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

CHARGING_CURRENT_ENTITY_ID = "number.garage_charging_current"
LCD_BRIGHTNESS_ENTITY_ID = "number.garage_lcd_brightness"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test number entity state and registry data."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_besen_client.async_start.assert_awaited_once()


async def test_number_updates_from_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test number state updates from client push data."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    publish_besen_state(mock_besen_client, charger_state(charge_amps=20))
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == "20"


async def test_number_updates_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test number state updates when the coordinator refreshes."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    mock_besen_client.state = charger_state(charge_amps=20)
    await async_update_entity(hass, CHARGING_CURRENT_ENTITY_ID)
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == "20"


@pytest.mark.parametrize(
    ("available", "authenticated"),
    [
        (False, True),
        (True, False),
    ],
)
async def test_number_unavailable_from_client_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    available: bool,
    authenticated: bool,
) -> None:
    """Test number availability follows client availability and authentication."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    publish_besen_state(
        mock_besen_client,
        charger_state(available=available, authenticated=authenticated),
    )
    await hass.async_block_till_done()

    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_number_unknown_without_reported_current(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test the number is unknown before the charger reports its current."""

    mock_besen_client.state = charger_state(charge_amps=None)

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("output_max_amps", "expected_max"),
    [
        (16, 16),
        (None, FALLBACK_MAX_CHARGE_AMPS),
    ],
)
async def test_number_maximum(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    output_max_amps: int | None,
    expected_max: int,
) -> None:
    """Test the maximum uses charger information with a safe fallback."""

    mock_besen_client.state = charger_state(
        charge_amps=16,
        output_max_amps=output_max_amps,
    )

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_MAX] == expected_max


async def test_number_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test setting the charging current calls the client and updates state."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CHARGING_CURRENT_ENTITY_ID, ATTR_VALUE: 20},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_besen_client.async_set_charge_amps.assert_awaited_once_with(20)
    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == "20"


async def test_number_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test command failures are translated to Home Assistant errors."""

    mock_besen_client.async_set_charge_amps = AsyncMock(
        side_effect=CommandFailed("failed")
    )

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: CHARGING_CURRENT_ENTITY_ID, ATTR_VALUE: 20},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
    state = hass.states.get(CHARGING_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == "16"


async def test_lcd_brightness_set_value(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test setting the LCD brightness calls the client and updates state."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: LCD_BRIGHTNESS_ENTITY_ID, ATTR_VALUE: 75},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_besen_client.async_set_lcd_brightness.assert_awaited_once_with(75)
    state = hass.states.get(LCD_BRIGHTNESS_ENTITY_ID)
    assert state is not None
    assert state.state == "75"


async def test_lcd_brightness_unknown_without_reported_value(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test LCD brightness is unknown before the charger reports it."""

    mock_besen_client.state = charger_state(lcd_brightness=None)

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    state = hass.states.get(LCD_BRIGHTNESS_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_lcd_brightness_command_failure(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test LCD brightness command failures are translated."""

    mock_besen_client.async_set_lcd_brightness = AsyncMock(
        side_effect=CommandFailed("failed")
    )

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: LCD_BRIGHTNESS_ENTITY_ID, ATTR_VALUE: 75},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
    state = hass.states.get(LCD_BRIGHTNESS_ENTITY_ID)
    assert state is not None
    assert state.state == "50"
