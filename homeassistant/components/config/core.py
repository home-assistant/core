"""Component to interact with Hassbian tools."""

from homeassistant.components.http import HomeAssistantView
from homeassistant.config import async_check_ha_config_file


async def async_setup(hass):
    """Set up the Hassbian config."""
    hass.http.register_view(CheckConfigView)
    return True


class CheckConfigView(HomeAssistantView):
    """Hassbian packages endpoint."""

    url = '/api/config/core/check_config'
    name = 'api:config:core:check_config'

    async def post(self, request):
        """Validate configuration and return results."""
        errors = await async_check_ha_config_file(request.app['hass'])

        state = 'invalid' if errors else 'valid'

        return self.json({
            "result": state,
            "errors": errors,
        })
