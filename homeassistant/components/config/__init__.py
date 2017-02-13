"""Component to interact with Hassbian tools."""
import asyncio

from homeassistant.core import callback
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.bootstrap import (
    async_prepare_setup_platform, ATTR_COMPONENT)
from homeassistant.components.frontend import register_built_in_panel

DOMAIN = 'config'
DEPENDENCIES = ['http']
SECTIONS = ('core', 'hassbian')
ON_DEMAND = ('zwave', )


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the hassbian component."""
    register_built_in_panel(hass, 'config', 'Configuration', 'mdi:settings')

    @asyncio.coroutine
    def setup_panel(panel_name):
        """Setup a panel."""
        panel = yield from async_prepare_setup_platform(hass, config, DOMAIN,
                                                        panel_name)

        if not panel:
            return

        success = yield from panel.async_setup(hass)

        if success:
            key = '{}.{}'.format(DOMAIN, panel_name)
            hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: key})
            hass.config.components.add(key)

    tasks = [setup_panel(panel_name) for panel_name in SECTIONS]

    for panel_name in ON_DEMAND:
        if panel_name in hass.config.components:
            tasks.append(setup_panel(panel_name))

    if tasks:
        yield from asyncio.wait(tasks, loop=hass.loop)

    @callback
    def component_loaded(event):
        """Respond to components being loaded."""
        panel_name = event.data.get(ATTR_COMPONENT)

        if panel_name in ON_DEMAND:
            setup_panel(panel_name)

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, component_loaded)

    return True
