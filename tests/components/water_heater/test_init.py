"""The tests for the water heater component."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.water_heater import (
    SET_TEMPERATURE_SCHEMA,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.core import HomeAssistant

from tests.common import async_mock_service


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"hvac_mode": "off", "entity_id": ["climate.test_id"]}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_set_temp_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with ok required data."""
    domain = "water_heater"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {
        "temperature": 20.0,
        "operation_mode": "gas",
        "entity_id": ["water_heater.test_id"],
    }
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


class MockWaterHeaterEntity(WaterHeaterEntity):
    """Mock water heater device to use in tests."""

    _attr_operation_list: list[str] = ["off", "heat_pump", "gas"]
    _attr_operation = "heat_pump"
    _attr_supported_features = WaterHeaterEntityFeature.ON_OFF


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    water_heater = MockWaterHeaterEntity()
    water_heater.hass = hass

    # Test with turn_on method defined
    setattr(water_heater, "turn_on", MagicMock())
    await water_heater.async_turn_on()

    assert water_heater.turn_on.call_count == 1

    # Test with async_turn_on method defined
    setattr(water_heater, "async_turn_on", AsyncMock())
    await water_heater.async_turn_on()

    assert water_heater.async_turn_on.call_count == 1


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    water_heater = MockWaterHeaterEntity()
    water_heater.hass = hass

    # Test with turn_off method defined
    setattr(water_heater, "turn_off", MagicMock())
    await water_heater.async_turn_off()

    assert water_heater.turn_off.call_count == 1

    # Test with async_turn_off method defined
    setattr(water_heater, "async_turn_off", AsyncMock())
    await water_heater.async_turn_off()

    assert water_heater.async_turn_off.call_count == 1
