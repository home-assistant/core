"""Tests for the Enphase Envoy integration."""
from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy import async_remove_config_entry_device
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def hass():
    """Fixture for setting up a Home Assistant instance."""
    hass = HomeAssistant()
    hass.data[DOMAIN] = {
        'entry_id': {
            'coordinator': 'mock_coordinator',
            'envoy_data': {'inverters_production': ['12345']}
        }
    }
    return hass

def test_async_remove_config_entry_device(hass):
    config_entry = ConfigEntry(
        unique_id='12345',
        entry_id='entry_id',
        data={},
        options={}
    )
    device_entry = {
        'identifiers': [('enphase_envoy', '12345')],
        'name': 'test device',
        'manufacturer': 'test manufacturer'
    }
    assert async_remove_config_entry_device(hass, config_entry, device_entry) == False
    device_entry = {
        'identifiers': [('enphase_envoy', '56789')],
        'name': 'test device',
        'manufacturer': 'test manufacturer'
    }
    assert async_remove_config_entry_device(hass, config_entry, device_entry) == True

