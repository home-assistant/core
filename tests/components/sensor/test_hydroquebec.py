"""The test for the hydroquebec sensor platform."""
import asyncio
import sys
from unittest.mock import MagicMock


from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor import hydroquebec
from tests.common import assert_setup_component


CONTRACT = "123456789"


class HydroQuebecClientMock(MagicMock):
    """Fake Hydroquebec client."""

    def __init__(self, username, password, contract=None):
        """Fake Hydroquebec client init."""
        pass

    def get_data(self, contract):
        """Return fake hydroquebec data."""
        return {CONTRACT: {"balance": 160.12}}

    def get_contracts(self):
        """Return fake hydroquebec contracts."""
        return [CONTRACT]

    @asyncio.coroutine
    def fetch_data(self):
        """Return fake fetching data."""
        pass


class HydroQuebecClientMockError(MagicMock):
    """Fake Hydroquebec client error."""

    def get_data(self, contract):
        """Return fake hydroquebec data."""
        return {CONTRACT: {"balance": 160.12}}

    @asyncio.coroutine
    def get_contracts(self):
        """Return fake hydroquebec contracts."""
        raise PyHydroQuebecErrorMock("Fake Error")

    @asyncio.coroutine
    def fetch_data(self):
        """Return fake fetching data."""
        if hasattr(self, 'data_fetched'):
            raise PyHydroQuebecErrorMock("Fake Error")
        self.data_fetched = True


class PyHydroQuebecError(BaseException):
    """Fake PyHydroquebec Error."""


class PyHydroQuebecErrorMock(BaseException):
    """Fake PyHydroquebec Error."""


@asyncio.coroutine
def test_hydroquebec_sensor(loop, hass):
    """Test the Hydroquebec number sensor."""
    sys.modules['pyhydroquebec'] = MagicMock()
    sys.modules['pyhydroquebec.client'] = MagicMock()
    sys.modules['pyhydroquebec.client.PyHydroQuebecError'] = \
        PyHydroQuebecErrorMock
    import pyhydroquebec.client
    pyhydroquebec.HydroQuebecClient = HydroQuebecClientMock
    pyhydroquebec.client.PyHydroQuebecError = PyHydroQuebecErrorMock
    config = {
        'sensor': {
            'platform': 'hydroquebec',
            'name': 'hydro',
            'contract': CONTRACT,
            'username': 'myusername',
            'password': 'password',
            'monitored_variables': [
                'balance',
            ],
        }
    }
    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', config)
    state = hass.states.get('sensor.hydro_balance')
    yield from hass.async_block_till_done()
    assert state.state == "160.12"
    assert state.attributes.get('unit_of_measurement') == "CAD"


@asyncio.coroutine
def test_hydroquebec_sensor_2(hass):
    """Test the Hydroquebec sensor errors."""
    sys.modules['pyhydroquebec'] = MagicMock()
    sys.modules['pyhydroquebec.client'] = MagicMock()
    import pyhydroquebec.client
    pyhydroquebec.client = MagicMock()
    pyhydroquebec.HydroQuebecClient = HydroQuebecClientMockError
    pyhydroquebec.client.PyHydroQuebecError = PyHydroQuebecErrorMock
    config = {
        'sensor': {
            'platform': 'hydroquebec',
            'name': 'hydro',
            'contract': CONTRACT,
            'username': 'myusername',
            'password': 'password',
            'monitored_variables': [
                'balance',
            ],
        }
    }
    ret = yield from hydroquebec.async_setup_platform(hass, config,
                                                      MagicMock())
    assert ret is False

    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', config)
