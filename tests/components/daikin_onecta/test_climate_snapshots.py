"""Snapshot tests for Daikin Onecta climate entities."""

from unittest.mock import call

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    ClimateEntityStateAttribute,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.core import HomeAssistant

from .conftest import MockOnectaClient
from .platform_helpers import _async_setup_fixture


async def test_fan_mode_changes_with_hvac_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Update the fan state from each native HVAC operation mode."""
    await _async_setup_fixture(hass, config_entry, "fanmode")
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            "entity_id": entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "3"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            "entity_id": entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.DRY,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.DRY
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "auto"
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            "00000000-0000-4000-8000-000000000101",
            "climateControl",
            "onOffMode",
            "on",
            path=None,
        ),
        call(
            "00000000-0000-4000-8000-000000000101",
            "climateControl",
            "operationMode",
            "cooling",
            path=None,
        ),
        call(
            "00000000-0000-4000-8000-000000000101",
            "climateControl",
            "operationMode",
            "dry",
            path=None,
        ),
    ]
