"""The tests for the climate component."""
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.climate import SET_TEMPERATURE_SCHEMA, ClimateDevice
from tests.common import async_mock_service


async def test_set_temp_schema_no_req(hass, caplog):
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


async def test_set_temp_schema(hass, caplog):
    """Test the set temperature schema with ok required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"temperature": 20.0, "hvac_mode": "heat", "entity_id": ["climate.test_id"]}
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


async def test_sync_turn_on(hass):
    """Test if adding turn_on work."""
    climate = ClimateDevice()
    climate.hass = hass

    climate.turn_on = MagicMock()
    await climate.async_turn_on()

    assert climate.turn_on.called


async def test_sync_turn_off(hass):
    """Test if adding turn_on work."""
    climate = ClimateDevice()
    climate.hass = hass

    climate.turn_off = MagicMock()
    await climate.async_turn_off()

    assert climate.turn_off.called
