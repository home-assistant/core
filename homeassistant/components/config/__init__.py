"""Component to configure Home Assistant via an API."""
import asyncio
import os

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.setup import (
    async_prepare_setup_platform, ATTR_COMPONENT)
from homeassistant.components.frontend import register_built_in_panel
from homeassistant.components.http import HomeAssistantView
from homeassistant.util.yaml import load_yaml, dump

DOMAIN = 'config'
DEPENDENCIES = ['http']
SECTIONS = ('core', 'group', 'hassbian')
ON_DEMAND = ('zwave', )


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the config component."""
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
            hass.async_add_job(setup_panel(panel_name))

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, component_loaded)

    return True


class EditKeyBasedConfigView(HomeAssistantView):
    """Configure a Group endpoint."""

    def __init__(self, component, config_type, path, key_schema, data_schema,
                 *, post_write_hook=None):
        """Initialize a config view."""
        self.url = '/api/config/%s/%s/{config_key}' % (component, config_type)
        self.name = 'api:config:%s:%s' % (component, config_type)
        self.path = path
        self.key_schema = key_schema
        self.data_schema = data_schema
        self.post_write_hook = post_write_hook

    @asyncio.coroutine
    def get(self, request, config_key):
        """Fetch device specific config."""
        hass = request.app['hass']
        current = yield from hass.loop.run_in_executor(
            None, _read, hass.config.path(self.path))
        return self.json(current.get(config_key, {}))

    @asyncio.coroutine
    def post(self, request, config_key):
        """Validate config and return results."""
        try:
            data = yield from request.json()
        except ValueError:
            return self.json_message('Invalid JSON specified', 400)

        try:
            self.key_schema(config_key)
        except vol.Invalid as err:
            return self.json_message('Key malformed: {}'.format(err), 400)

        try:
            # We just validate, we don't store that data because
            # we don't want to store the defaults.
            self.data_schema(data)
        except vol.Invalid as err:
            return self.json_message('Message malformed: {}'.format(err), 400)

        hass = request.app['hass']
        path = hass.config.path(self.path)

        current = yield from hass.loop.run_in_executor(None, _read, path)
        current.setdefault(config_key, {}).update(data)

        yield from hass.loop.run_in_executor(None, _write, path, current)

        if self.post_write_hook is not None:
            hass.async_add_job(self.post_write_hook(hass))

        return self.json({
            'result': 'ok',
        })


def _read(path):
    """Read YAML helper."""
    if not os.path.isfile(path):
        with open(path, 'w'):
            pass
        return {}

    return load_yaml(path)


def _write(path, data):
    """Write YAML helper."""
    # Do it before opening file. If dump causes error it will now not
    # truncate the file.
    data = dump(data)
    with open(path, 'w', encoding='utf-8') as outfile:
        outfile.write(data)
