"""The test for the hydroquebec sensor platform."""
import asyncio
import logging
import sys
from unittest.mock import MagicMock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor import hydroquebec
from tests.common import assert_setup_component


CONTRACT = "123456789"


class HydroQuebecClientMock():
    """Fake Hydroquebec client."""

    def __init__(self, username, password, contract=None, httpsession=None):
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


class HydroQuebecClientMockError(HydroQuebecClientMock):
    """Fake Hydroquebec client error."""

    def get_contracts(self):
        """Return fake hydroquebec contracts."""
        return []

    @asyncio.coroutine
    def fetch_data(self):
        """Return fake fetching data."""
        raise PyHydroQuebecErrorMock("Fake Error")


class PyHydroQuebecErrorMock(BaseException):
    """Fake PyHydroquebec Error."""


class PyHydroQuebecClientFakeModule():
    """Fake pyfido.client module."""

    PyHydroQuebecError = PyHydroQuebecErrorMock


class PyHydroQuebecFakeModule():
    """Fake pyfido module."""

    HydroQuebecClient = HydroQuebecClientMockError


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
    assert state.state == "160.12"
    assert state.attributes.get('unit_of_measurement') == "CAD"


@asyncio.coroutine
def test_error(hass, caplog):
    """Test the Hydroquebec sensor errors."""
    caplog.set_level(logging.ERROR)
    sys.modules['pyhydroquebec'] = PyHydroQuebecFakeModule()
    sys.modules['pyhydroquebec.client'] = PyHydroQuebecClientFakeModule()

    config = {}
    fake_async_add_devices = MagicMock()
    yield from hydroquebec.async_setup_platform(hass, config,
                                                fake_async_add_devices)
    assert fake_async_add_devices.called is False
