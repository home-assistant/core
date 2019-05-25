"""Test the Luftdaten component setup."""
from unittest.mock import patch

from homeassistant.components import luftdaten
from homeassistant.components.luftdaten.const import CONF_SENSOR_ID, DOMAIN
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_SHOW_ON_MAP
from homeassistant.setup import async_setup_component


async def test_config_with_sensor_passed_to_config_entry(hass):
    """Test that configured options for a sensor are loaded."""
    conf = {
        CONF_SENSOR_ID: '12345abcde',
        CONF_SHOW_ON_MAP: False,
        CONF_SCAN_INTERVAL: 600,
    }

    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(luftdaten, 'configured_sensors', return_value=[]):
        assert await async_setup_component(hass, DOMAIN, conf) is True

    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered sensor does not initiate an import."""
    conf = {
        CONF_SENSOR_ID: '12345abcde',
    }

    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(luftdaten, 'configured_sensors',
                         return_value=['12345abcde']):
        assert await async_setup_component(hass, DOMAIN, conf) is True

    assert len(mock_config_entries.flow.mock_calls) == 0
