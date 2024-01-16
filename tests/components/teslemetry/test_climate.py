"""Test the teslemetry climate platform."""

from syrupy import SnapshotAssertion
from tesla_fleet_api.exceptions import TeslaFleetError

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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_climate(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    snapshot: SnapshotAssertion,
    teslemetry_vehicle_specific_mock,
) -> None:
    """Tests that the climate entity is correct."""

    config_entry_mock.add_to_hass(hass)
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == snapshot(name="all")

    entity_id = "climate.test_climate"
    assert hass.states.get(entity_id) == snapshot

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    assert hass.states.get(entity_id) == snapshot

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 20.5},
        blocking=True,
    )
    assert hass.states.get(entity_id) == snapshot

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: "keep"},
        blocking=True,
    )
    assert hass.states.get(entity_id) == snapshot

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    assert hass.states.get(entity_id) == snapshot


async def test_errors(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    teslemetry_vehicle_specific_mock,
) -> None:
    """Tests API errors are handled."""

    config_entry_mock.add_to_hass(hass)

    # Test setting climate on with unknown error
    entity_id = "climate.test_climate"
    teslemetry_vehicle_specific_mock.set_temps.side_effect = TeslaFleetError
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
