"""Example component to show how config entries work."""

import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.util import slugify


DOMAIN = 'config_entry_example'


@asyncio.coroutine
def async_setup(hass, config):
    """Setup for our example component."""
    return True


@asyncio.coroutine
def async_setup_entry(hass, entry):
    """Initialize an entry."""
    entity_id = '{}.{}'.format(DOMAIN, entry.data['object_id'])
    hass.states.async_set(entity_id, 'loaded', {
        ATTR_FRIENDLY_NAME: entry.data['name']
    })

    # Indicate setup was successful.
    return True


@asyncio.coroutine
def async_unload_entry(hass, entry):
    """Unload an entry."""
    entity_id = '{}.{}'.format(DOMAIN, entry.data['object_id'])
    hass.states.async_remove(entity_id)

    # Indicate unload was successful.
    return True


@config_entries.HANDLERS.register(DOMAIN)
class ExampleConfigFlow(config_entries.ConfigFlowHandler):
    """Handle an example configuration flow."""

    VERSION = 1

    def __init__(self):
        """Initialize a Hue config handler."""
        self.object_id = None

    @asyncio.coroutine
    def async_step_init(self, user_input=None):
        """Start config flow."""
        errors = None
        if user_input is not None:
            object_id = user_input['object_id']

            if object_id != '' and object_id == slugify(object_id):
                self.object_id = user_input['object_id']
                return (yield from self.async_step_name())

            errors = {
                'object_id': 'Invalid object id.'
            }

        return self.async_show_form(
            title='Pick object id',
            step_id='init',
            description="Please enter an object_id for the test entity.",
            data_schema=vol.Schema({
                'object_id': str
            }),
            errors=errors
        )

    @asyncio.coroutine
    def async_step_name(self, user_input=None):
        """Ask user to enter the name."""
        errors = None
        if user_input is not None:
            name = user_input['name']

            if name != '':
                return self.async_create_entry(
                    title=name,
                    data={
                        'name': name,
                        'object_id': self.object_id,
                    }
                )

        return self.async_show_form(
            title='Name of the entity',
            step_id='name',
            description="Please enter a name for the test entity.",
            data_schema=vol.Schema({
                'name': str
            }),
            errors=errors
        )
