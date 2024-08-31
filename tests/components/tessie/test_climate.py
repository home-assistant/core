"""Test the Tessie climate platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.tessie.const import TessieClimateKeeper
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import (
    ERROR_UNKNOWN,
    TEST_RESPONSE,
    TEST_VEHICLE_STATE_ONLINE,
    setup_platform,
)


async def test_climate(hass: HomeAssistant) -> None:
    """Tests that the climate entity is correct."""

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 1

    entity_id = "climate.test_climate"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert (
        state.attributes.get(ATTR_MIN_TEMP)
        == TEST_VEHICLE_STATE_ONLINE["climate_state"]["min_avail_temp"]
    )
    assert (
        state.attributes.get(ATTR_MAX_TEMP)
        == TEST_VEHICLE_STATE_ONLINE["climate_state"]["max_avail_temp"]
    )

    # Test setting climate on
    with patch(
        "homeassistant.components.tessie.climate.start_climate_preconditioning",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )
        mock_set.assert_called_once()

    # Test setting climate temp
    with patch(
        "homeassistant.components.tessie.climate.set_temperature",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 20},
            blocking=True,
        )
        mock_set.assert_called_once()

    # Test setting climate preset
    with patch(
        "homeassistant.components.tessie.climate.set_climate_keeper_mode",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: TessieClimateKeeper.ON},
            blocking=True,
        )
        mock_set.assert_called_once()

    # Test setting climate off
    with patch(
        "homeassistant.components.tessie.climate.stop_climate",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
        mock_set.assert_called_once()


async def test_errors(hass: HomeAssistant) -> None:
    """Tests virtual key error is handled."""

    await setup_platform(hass)
    entity_id = "climate.test_climate"

    # Test setting climate on with unknown error
    with patch(
        "homeassistant.components.tessie.climate.start_climate_preconditioning",
        side_effect=ERROR_UNKNOWN,
    ) as mock_set, pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_set.assert_called_once()
        assert error.from_exception == ERROR_UNKNOWN
