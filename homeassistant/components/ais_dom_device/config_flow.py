"""Config flow to configure the AIS Spotify Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
import asyncio
import logging
G_AUTH_URL = None
_LOGGER = logging.getLogger(__name__)


def setUrl(url):
    global G_AUTH_URL
    G_AUTH_URL = url


def check_scanning_resoult(hass, loop) -> int:
    import time
    _LOGGER.info('loop: ' + str(loop))
    iot_dev = hass.states.get('input_select.ais_iot_devices_in_network')
    iot_dev_to_add = len(iot_dev.attributes['options'])
    time.sleep(5)
    return iot_dev_to_add


@callback
def configured_service(hass):
    """Return a set of the configured hosts."""
    return set('spotify' for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class AisDomDeviceFlowHandler(config_entries.ConfigFlow):
    """Spotify config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_one(user_input=None)
        return self.async_show_form(
            step_id='confirm',
            errors=errors,
        )

    async def async_step_one(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_two(user_input=None)
        return self.async_show_form(
            step_id='one',
            errors=errors,
        )

    async def async_step_two(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_three(user_input=None)
        return self.async_show_form(
            step_id='two',
            errors=errors,
        )

    async def async_step_three(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        for x in range(0, 5):
            result = await self.hass.async_add_executor_job(check_scanning_resoult, self.hass, x)
            _LOGGER.info(str(result))
            if result > 1:
                return await self.async_step_init(user_input=None)
            else:
                errors = {'devices': 'search_failed'}

        user_input['devices'] = ' '
        return self.async_show_form(
            step_id='two',
            errors=errors,
            data=user_input
        )   

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Dodano nowe urządzenie",
                data=user_input
            )

        return self.async_show_form(
            step_id='init',
            errors=errors,
            description_placeholders={
                'auth_url': G_AUTH_URL,
            },
        )



