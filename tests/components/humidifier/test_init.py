"""The tests for the humidifier component."""
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.humidifier import SET_HUMIDITY_SCHEMA, HumidifierDevice
from tests.common import async_mock_service


async def test_set_hum_schema_no_req(hass, caplog):
    """Test the set humidity schema with missing required data."""
    domain = "humidifier"
    service = "test_set_humidity"
    schema = SET_HUMIDITY_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"entity_id": ["humidifier.test_id"]}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_set_hum_schema(hass, caplog):
    """Test the set humidity schema with ok required data."""
    domain = "humidifier"
    service = "test_set_humidity"
    schema = SET_HUMIDITY_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"humidity": 50.0, "entity_id": ["humidifier.test_id"]}
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


async def test_sync_turn_on(hass):
    """Test if adding turn_on work."""
    humidifier = HumidifierDevice()
    humidifier.hass = hass

    humidifier.turn_on = MagicMock()
    await humidifier.async_turn_on()

    assert humidifier.turn_on.called


async def test_sync_turn_off(hass):
    """Test if adding turn_off work."""
    humidifier = HumidifierDevice()
    humidifier.hass = hass

    humidifier.turn_off = MagicMock()
    await humidifier.async_turn_off()

    assert humidifier.turn_off.called
