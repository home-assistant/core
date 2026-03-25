"""Test the Tessie climate platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    HVACMode,
)
from homeassistant.components.tessie.const import TessieClimateKeeper
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import TEST_RESPONSE, assert_entities, setup_platform


async def test_climate(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the climate entity is correct."""

    entry = await setup_platform(hass, [Platform.CLIMATE])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    entity_id = "climate.test_climate"

    with patch(
        "tesla_fleet_api.tessie.Vehicle.start_climate",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert hass.states.get(entity_id).state == HVACMode.HEAT_COOL

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.set_temperatures",
            return_value=TEST_RESPONSE,
        ) as mock_set,
        patch(
            "tesla_fleet_api.tessie.Vehicle.start_climate",
            return_value=TEST_RESPONSE,
        ) as mock_set2,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: [entity_id],
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
                ATTR_TEMPERATURE: 20,
            },
            blocking=True,
        )
        mock_set.assert_called_once()
        mock_set2.assert_called_once()
    assert hass.states.get(entity_id).attributes[ATTR_TEMPERATURE] == 20

    with patch(
        "tesla_fleet_api.tessie.Vehicle.tessie_set_climate_keeper_mode",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: TessieClimateKeeper.ON},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert (
        hass.states.get(entity_id).attributes[ATTR_PRESET_MODE]
        == TessieClimateKeeper.ON
    )

    with patch(
        "tesla_fleet_api.tessie.Vehicle.stop_climate",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert hass.states.get(entity_id).state == HVACMode.OFF


async def test_errors(hass: HomeAssistant) -> None:
    """Tests errors are handled."""

    await setup_platform(hass, [Platform.CLIMATE])
    entity_id = "climate.test_climate"

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.stop_climate",
            side_effect=TeslaFleetError,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_set.assert_called_once()
    assert isinstance(error.value.__cause__, TeslaFleetError)

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.start_climate",
            return_value={"response": {"result": False, "reason": "cpd_enabled"}},
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )
    mock_set.assert_called_once()
    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == "cpd_enabled"
