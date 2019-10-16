from datetime import date

import pytest
import voluptuous
from pymultimatic.model import QuickModes

from homeassistant.components import vaillant
from tests.components.vaillant import _setup, SystemManagerMock, _call_service
from homeassistant.components.vaillant import DOMAIN


@pytest.fixture(autouse=True)
def fixture_only_binary_sensor(mock_system_manager):
    """Mock vaillant to only handle binary_sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = []
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await _setup(hass)
    assert len(hass.services.async_services()[DOMAIN]) == 4


async def test_remove_quick_mode(hass):
    assert await _setup(hass)
    await _call_service(hass, 'vaillant', 'remove_quick_mode', None)
    SystemManagerMock.instance.remove_quick_mode.assert_called_once_with()


async def test_remove_quick_mode_wrong_data(hass):
    assert await _setup(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await _call_service(hass, 'vaillant', 'remove_quick_mode',
                            {'test': 'boom'})


async def test_remove_holiday_mode(hass):
    assert await _setup(hass)
    await _call_service(hass, 'vaillant', 'remove_holiday_mode', None)
    SystemManagerMock.instance.remove_holiday_mode.assert_called_once_with()


async def test_remove_holiday_mode_wrong_data(hass):
    assert await _setup(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await _call_service(hass, 'vaillant', 'remove_holiday_mode',
                            {'test': 'boom'})


async def test_set_quick_mode(hass):
    assert await _setup(hass)
    await _call_service(hass, 'vaillant', 'set_quick_mode',
                        {'quick_mode': 'QM_PARTY'})
    SystemManagerMock.instance\
        .set_quick_mode.assert_called_once_with(QuickModes.PARTY)


async def test_set_quick_mode_wrong_data(hass):
    assert await _setup(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await _call_service(hass, 'vaillant', 'set_quick_mode', {'test': 'boom'})


async def test_set_holiday_mode(hass):
    assert await _setup(hass)
    await _call_service(hass, 'vaillant', 'set_holiday_mode', {
        'start_date': '2010-10-25',
        'end_date': '2010-10-26',
        'temperature': '10'
    })
    SystemManagerMock.instance\
        .set_quick_mode.set_holiday_mode(date(2010, 10, 25),
                                         date(2010, 10, 26),
                                         10.0)


async def test_set_holiday_mode_wrong_data(hass):
    assert await _setup(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await _call_service(hass, 'vaillant', 'set_holiday_mode',
                            {'test': 'boom'})
