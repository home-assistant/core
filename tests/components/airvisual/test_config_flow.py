"""Define tests for the AirVisual config flow."""
import pytest
from pyairvisual.errors import AirVisualError

from homeassistant import data_entry_flow
from homeassistant.components.airvisual import DOMAIN, config_flow
from homeassistant.const import (
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_SCAN_INTERVAL)

from tests.common import MockConfigEntry, MockDependency, mock_coro


@pytest.fixture
def nearest_city_response():
    """Define a fixture for a successful /nearest_city response."""
    return mock_coro()


@pytest.fixture
def mock_pyairvisual(nearest_city_response):
    """Mock the pyairvisual library."""
    with MockDependency('pyairvisual') as mock_pyairvisual_:
        mock_pyairvisual_.Client(
        ).data.nearest_city.return_value = nearest_city_response
        yield mock_pyairvisual_


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    MockConfigEntry(
        domain=DOMAIN, data=conf,
        title='39.128712, -104.9812612').add_to_hass(hass)
    flow = config_flow.AirVisualFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {'base': 'identifier_exists'}


@pytest.mark.parametrize(
    'nearest_city_response', [mock_coro(exception=AirVisualError)])
async def test_invalid_api_key(hass, mock_pyairvisual):
    """Test that an invalid API key throws an error."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.AirVisualFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {CONF_API_KEY: 'invalid_api_key'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AirVisualFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

async def test_step_import(hass, mock_pyairvisual):
    """Test that the import step works."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.AirVisualFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '39.128712, -104.9812612'
    assert result['data'] == {
        CONF_API_KEY: '12345abcde',
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_SCAN_INTERVAL: 600
    }

async def test_step_user(hass, mock_pyairvisual):
    """Test that the user step works."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.AirVisualFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '39.128712, -104.9812612'
    assert result['data'] == {
        CONF_API_KEY: '12345abcde',
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_SCAN_INTERVAL: 600
    }
