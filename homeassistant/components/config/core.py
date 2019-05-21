"""Component to interact with Hassbian tools."""

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.config import async_check_ha_config_file
from homeassistant.components import websocket_api


async def async_setup(hass):
    """Set up the Hassbian config."""
    hass.http.register_view(CheckConfigView)
    hass.components.websocket_api.async_register_command(websocket_core_update)
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


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'config/core/update',
    vol.Optional('latitude'): vol.Coerce(float),
    vol.Optional('longitude'): vol.Coerce(float),
    vol.Optional('elevation'): vol.Coerce(int),
    vol.Optional('unit_system'): vol.Coerce(str),
    vol.Optional('location_name'): vol.Coerce(str),
    vol.Optional('time_zone'): vol.Coerce(str),
})
async def websocket_core_update(hass, connection, msg):
    """Handle request for account info."""
    data = dict(msg)
    data.pop('id')
    data.pop('type')
    await hass.config.update(**data)
    connection.send_result(msg['id'])
