"""Component to interact with Hassbian tools."""
import asyncio

from homeassistant.components.http import HomeAssistantView
from homeassistant.config import async_check_ha_config_file


@asyncio.coroutine
def async_setup(hass):
    """Set up the Hassbian config."""
    hass.http.register_view(CheckConfigView)
    return True


class CheckConfigView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = '/api/config/core/check_config'
    name = 'api:config:core:check_config'

    @asyncio.coroutine
    def post(self, request):
        """Validate configuration and return results."""
        hass = request.app['hass']

        if hass.components.hassio.is_hassio():
            errors = yield from hass.components.hassio.async_check_config()
        else:
            errors = yield from async_check_ha_config_file(hass)

        state = 'invalid' if errors else 'valid'

        return self.json({
            "result": state,
            "errors": errors,
        })
