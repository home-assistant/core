"""Component to interact with Hassbian tools."""
import json
import os

from homeassistant.components.http import HomeAssistantView


_TEST_OUTPUT = """
{
    "suites":{
        "libcec":{
            "state":"Uninstalled",
            "description":"Installs the libcec package for controlling CEC devices from this Pi"
        },
        "mosquitto":{
            "state":"failed",
            "description":"Installs the Mosquitto package for setting up a local MQTT server"
        },
        "openzwave":{
            "state":"Uninstalled",
            "description":"Installs the Open Z-wave package for setting up your zwave network"
        },
        "samba":{
            "state":"installing",
            "description":"Installs the samba package for sharing the hassbian configuration files over the Pi's network."
        }
    }
}
"""  # noqa


async def async_setup(hass):
    """Set up the Hassbian config."""
    # Test if is Hassbian
    test_mode = 'FORCE_HASSBIAN' in os.environ
    is_hassbian = test_mode

    if not is_hassbian:
        return False

    hass.http.register_view(HassbianSuitesView(test_mode))
    hass.http.register_view(HassbianSuiteInstallView(test_mode))

    return True


async def hassbian_status(hass, test_mode=False):
    """Query for the Hassbian status."""
    # Fetch real output when not in test mode
    if test_mode:
        return json.loads(_TEST_OUTPUT)

    raise Exception('Real mode not implemented yet.')


class HassbianSuitesView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = '/api/config/hassbian/suites'
    name = 'api:config:hassbian:suites'

    def __init__(self, test_mode):
        """Initialize suites view."""
        self._test_mode = test_mode

    async def get(self, request):
        """Request suite status."""
        inp = await hassbian_status(request.app['hass'], self._test_mode)

        return self.json(inp['suites'])


class HassbianSuiteInstallView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = '/api/config/hassbian/suites/{suite}/install'
    name = 'api:config:hassbian:suite'

    def __init__(self, test_mode):
        """Initialize suite view."""
        self._test_mode = test_mode

    async def post(self, request, suite):
        """Request suite status."""
        # do real install if not in test mode
        return self.json({"status": "ok"})
