"""Component to interact with Hassbian tools."""
import asyncio
import json
import os

from homeassistant.components.http import HomeAssistantView


_TEST_OUTPUT = """
{
  "suites": [
    {
      "openzwave": [
        {
          "state": "installed"
        },
        {
          "description": "This is the description of the Open Z-Wave suite."
        }
      ]
    },
    {
      "openelec": [
        {
          "state": "not_installed"
        },
        {
          "description":
          "OpenElec is amazing. It allows you to control the TV."
        }
      ]
    },
    {
      "mosquitto": [
        {
          "state": "installing"
        },
        {
          "description":
          "Mosquitto is an MQTT broker."
        }
      ]
    }
  ]
}
"""


@asyncio.coroutine
def async_setup(hass):
    """Setup the hassbian config."""
    # Test if is hassbian
    test_mode = 'FORCE_HASSBIAN' in os.environ
    is_hassbian = test_mode

    if not is_hassbian:
        return False

    hass.http.register_view(HassbianSuitesView(test_mode))
    hass.http.register_view(HassbianSuiteInstallView(test_mode))

    return True


@asyncio.coroutine
def hassbian_status(hass, test_mode=False):
    """Query for the Hassbian status."""
    # fetch real output when not in test mode
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

    @asyncio.coroutine
    def get(self, request):
        """Request suite status."""
        inp = yield from hassbian_status(request.app['hass'], self._test_mode)

        # Flatten the structure a bit
        suites = {}

        for suite in inp['suites']:
            key = next(iter(suite))
            info = suites[key] = {}

            for item in suite[key]:
                item_key = next(iter(item))
                info[item_key] = item[item_key]

        return self.json(suites)


class HassbianSuiteInstallView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = '/api/config/hassbian/suites/{suite}/install'
    name = 'api:config:hassbian:suite'

    def __init__(self, test_mode):
        """Initialize suite view."""
        self._test_mode = test_mode

    @asyncio.coroutine
    def post(self, request, suite):
        """Request suite status."""
        # do real install if not in test mode
        return self.json({"status": "ok"})
