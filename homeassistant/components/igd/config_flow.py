"""Config flow for IGD."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

import voluptuous as vol

from .const import DOMAIN
from .const import LOGGER as _LOGGER


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data['ssdp_url']
               for entry in hass.config_entries.async_entries(DOMAIN))


async def _get_igd_device(hass, ssdp_url):
    """."""
    # build requester
    from async_upnp_client.aiohttp import AiohttpSessionRequester
    session = async_get_clientsession(hass)
    requester = AiohttpSessionRequester(session, True)

    # create upnp device
    from async_upnp_client import UpnpFactory
    factory = UpnpFactory(requester, disable_state_variable_validation=True)
    try:
        upnp_device = await factory.async_create_device(ssdp_url)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    # wrap with IgdDevice
    from async_upnp_client.igd import IgdDevice
    igd_device = IgdDevice(upnp_device, None)
    return igd_device


@config_entries.HANDLERS.register(DOMAIN)
class IgdFlowHandler(data_entry_flow.FlowHandler):
    """Handle a Hue config flow."""

    VERSION = 1

    # def __init__(self):
    #     """Initializer."""
    #     self.host = None

    # flow: 1. detection/user adding
    #       2. question: port forward? sensors?
    #       3. add it!

    async def async_step_user(self, user_input=None):
        _LOGGER.debug('async_step_user: %s', user_input)
        return await self.async_abort(reason='todo')

    async def async_step_discovery(self, discovery_info):
        """Handle a discovered IGD.

        This flow is triggered by the discovery component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        _LOGGER.debug('async_step_discovery: %s', discovery_info)

        ssdp_url = discovery_info['ssdp_description']
        return await self.async_step_options({
            'ssdp_url': ssdp_url,
        })

    async def async_step_options(self, user_options):
        """."""
        _LOGGER.debug('async_step_options: %s', user_options)
        if user_options and \
           'sensors' in user_options and \
           'port_forward' in user_options:
            return await self.async_step_import(user_options)

        return self.async_show_form(
            step_id='options',
            data_schema=vol.Schema({
                vol.Required('sensors'): cv.boolean,
                vol.Required('port_forward'): cv.boolean,
                # vol.Optional('ssdp_url', default=user_options['ssdp_url']): cv.url,
            })
        )

    async def async_step_import(self, import_info):
        """Import a IGD as new entry."""
        _LOGGER.debug('async_step_import: %s', import_info)

        ssdp_url = import_info['ssdp_url']
        try:
            igd_device = await _get_igd_device(self.hass, ssdp_url)  # try it to see if it works
        except:
            pass
        return self.async_create_entry(
            title=igd_device.name,
            data={
                'ssdp_url': ssdp_url,
                'udn': igd_device.udn,
            }
        )