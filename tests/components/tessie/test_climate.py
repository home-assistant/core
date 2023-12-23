"""Test the Tessie climate platform."""
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ERROR_UNKNOWN, TEST_RESPONSE, setup_platform


async def test_climate(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the climate entity is correct."""

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 0

    await setup_platform(hass)

    assert hass.states.async_all(CLIMATE_DOMAIN) == snapshot(name="all")

    entity_id = "climate.test_climate"

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
    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}:on")

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
    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}:temperature")

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
    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}:preset")

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
    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}:off")


async def test_errors(hass: HomeAssistant) -> None:
    """Tests errors are handled."""

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
