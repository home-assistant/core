"""Define tests for the IQVIA config flow."""
from pyiqvia.errors import IQVIAError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.iqvia import CONF_ZIP_CODE, DOMAIN, config_flow

from tests.common import MockConfigEntry, MockDependency, mock_coro


@pytest.fixture
def allergens_current_response():
    """Define a fixture for a successful allergens.current response."""
    return mock_coro()


@pytest.fixture
def mock_pyiqvia(allergens_current_response):
    """Mock the pyiqvia library."""
    with MockDependency('pyiqvia') as mock_pyiqvia_:
        mock_pyiqvia_.Client().allergens.current.return_value = (
            allergens_current_response)
        yield mock_pyiqvia_


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_ZIP_CODE: '12345',
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {CONF_ZIP_CODE: 'identifier_exists'}


@pytest.mark.parametrize(
    'allergens_current_response', [mock_coro(exception=IQVIAError)])
async def test_invalid_zip_code(hass, mock_pyiqvia):
    """Test that an invalid ZIP code key throws an error."""
    conf = {
        CONF_ZIP_CODE: 'abcde',
    }

    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {CONF_ZIP_CODE: 'invalid_zip_code'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_import(hass, mock_pyiqvia):
    """Test that the import step works."""
    conf = {
        CONF_ZIP_CODE: '12345',
    }

    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '12345'
    assert result['data'] == {
        CONF_ZIP_CODE: '12345',
    }


async def test_step_user(hass, mock_pyiqvia):
    """Test that the user step works."""
    conf = {
        CONF_ZIP_CODE: '12345',
    }

    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '12345'
    assert result['data'] == {
        CONF_ZIP_CODE: '12345',
    }
