"""Tests for OpenERZ component."""
from copy import deepcopy
from unittest.mock import MagicMock, patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.setup import async_setup_component

MOCK_CONFIG = {
    "sensor": {
        "platform": "openerz",
        "name": "test_name",
        "zip": 1234,
        "waste_type": "glass",
    }
}


async def test_sensor_init(hass):
    """Test whether all values initialized properly."""
    with patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    ) as patched_update:
        await async_setup_component(hass, SENSOR_DOMAIN, MOCK_CONFIG)

        entity_id = "sensor.test_name"
        test_openerz = hass.data[SENSOR_DOMAIN].get_entity(entity_id)

        await hass.async_block_till_done()

        assert test_openerz.zip == 1234
        assert test_openerz.waste_type == "glass"
        assert test_openerz.friendly_name == "test_name"
        patched_update.assert_called_once()


async def test_sensor_init_missing_type(hass):
    """Test whether default waste type set properly."""
    mock_config_copy = deepcopy(MOCK_CONFIG)
    del mock_config_copy["sensor"]["waste_type"]
    with patch(
        "homeassistant.components.openerz.sensor.OpenERZSensor.update",
        return_value=True,
    ) as patched_update:
        await async_setup_component(hass, SENSOR_DOMAIN, mock_config_copy)

        entity_id = "sensor.test_name"
        test_openerz = hass.data[SENSOR_DOMAIN].get_entity(entity_id)

        await hass.async_block_till_done()

        assert test_openerz.zip == 1234
        assert test_openerz.waste_type == "waste"
        assert test_openerz.friendly_name == "test_name"
        patched_update.assert_called_once()


async def test_sensor_state(hass):
    """Test whether default waste type set properly."""
    with patch(
        "homeassistant.components.openerz.sensor.OpenERZConnector"
    ) as patched_connector:
        pickup_instance = MagicMock()
        pickup_instance.find_next_pickup.return_value = "2020-12-12"
        patched_connector.return_value = pickup_instance

        await async_setup_component(hass, SENSOR_DOMAIN, MOCK_CONFIG)

        entity_id = "sensor.test_name"
        test_openerz_state = hass.states.get(entity_id).state

        await hass.async_block_till_done()

        assert test_openerz_state == "2020-12-12"
        pickup_instance.find_next_pickup.assert_called_once()
