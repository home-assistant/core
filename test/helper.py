"""
test.helper
~~~~~~~~~~~

Helper method for writing tests.
"""
import os

import homeassistant as ha


def get_test_home_assistant():
    """ Returns a Home Assistant object pointing at test config dir. """
    hass = ha.HomeAssistant()
    hass.config_dir = os.path.join(os.path.dirname(__file__), "config")

    return hass


def mock_service(hass, domain, service):
    """
    Sets up a fake service.
    Returns a list that logs all calls to fake service.
    """
    calls = []

    hass.services.register(
        domain, service, lambda call: calls.append(call))

    return calls
