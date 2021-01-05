"""Configuration for AV Receiver tests."""
from pyavreceiver.dispatch import Dispatcher
import pytest

from homeassistant.components.avreceiver import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock HEOS config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, title="AV Receiver (127.0.0.1)"
    )


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_HOST: "127.0.0.1"}}


@pytest.fixture(name="dispatcher")
def dispatcher_fixture() -> Dispatcher:
    """Create a dispatcher for testing."""
    return Dispatcher()


# @pytest.fixture(name="factory")
# def factory_fixture():
#     """Create a mock AV Receiver factory."""
#     mock_factory = Mock(factory)
#     with patch("homeassistant.components.avreceiver.factory", new=)


# @pytest.fixture(name="avr")
# def avreceiver_fixture(dispatcher):
#     """Create a mock AV Receiver fixture."""
#     mock_avr = Mock(AVReceiver)
#     mock_avr.dispatcher = dispatcher
#     mock_avr.connection_state = const.STATE_CONNECTED
#     mock = Mock(return_value=mock_avr)

#     with patch("homeassistant.components.avreceiver.", new=mock), patch(
#         "homeassistant.components.avreceiver.config_flow.AVReceiver", new=mock
#     ):
#         yield mock_avr
