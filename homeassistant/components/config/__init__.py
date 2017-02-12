"""Component to interact with Hassbian tools."""
import asyncio

from homeassistant.bootstrap import async_prepare_setup_platform
from homeassistant.components.frontend import register_built_in_panel

DOMAIN = 'config'
DEPENDENCIES = ['http']


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the hassbian component."""
    register_built_in_panel(hass, 'config', 'Configuration', 'mdi:settings')

    for panel_name in ('hassbian',):
        panel = yield from async_prepare_setup_platform(hass, config, DOMAIN,
                                                        panel_name)

        if not panel:
            continue

        success = yield from panel.async_setup(hass)

        if success:
            hass.config.components.add('{}.{}'.format(DOMAIN, panel_name))

    return True
