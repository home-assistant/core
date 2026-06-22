"""Tests for the Schluter DITRA-HEAT climate entity."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.schluter.api import (
    CannotConnectError,
    InvalidSessionError,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .conftest import MOCK_SERIAL, MOCK_THERMOSTAT

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.bathroom"
UPDATE_INTERVAL = timedelta(minutes=3)


async def test_climate_entity_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that the climate entity reflects coordinator data correctly."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_TEMPERATURE] == 24.0
    assert state.attributes[ATTR_MIN_TEMP] == 5.0
    assert state.attributes[ATTR_MAX_TEMP] == 35.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.5


async def test_climate_entity_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that the entity reports IDLE when the thermostat is not heating."""
    mock_schluter_api.async_get_thermostats.return_value = [
        replace(MOCK_THERMOSTAT, is_heating=False)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_set_hvac_mode_is_noop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that set_hvac_mode does nothing (floor heating is always HEAT)."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT


async def test_set_temperature_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that set_temperature calls the API with the correct arguments."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    mock_schluter_api.async_set_temperature.assert_awaited_once_with(
        "test-session-id", MOCK_SERIAL, 22.0
    )


@pytest.mark.parametrize(
    "side_effect",
    [CannotConnectError, InvalidSessionError],
    ids=["cannot_connect", "invalid_session"],
)
async def test_set_temperature_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
    side_effect: type[Exception],
) -> None:
    """Test that API errors during set_temperature raise HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_schluter_api.async_set_temperature.side_effect = side_effect

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )


async def test_entity_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the coordinator cannot reach the API."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT

    mock_schluter_api.async_get_thermostats.side_effect = CannotConnectError

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_session_refresh_fails_with_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity becomes unavailable when re-auth succeeds but second fetch fails."""
    await setup_integration(hass, mock_config_entry)

    mock_schluter_api.async_get_thermostats.side_effect = [
        InvalidSessionError,
        CannotConnectError,
    ]

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_session_refresh_on_expiry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the coordinator re-authenticates silently when the session expires."""
    await setup_integration(hass, mock_config_entry)

    mock_schluter_api.async_get_thermostats.side_effect = [
        InvalidSessionError,
        [MOCK_THERMOSTAT],
    ]

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_schluter_api.async_get_session.call_count == 2
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT
