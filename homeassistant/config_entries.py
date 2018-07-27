"""The Config Manager is responsible for managing configuration for components.

The Config Manager allows for creating config entries to be consumed by
components. Each entry is created via a Config Flow Handler, as defined by each
component.

During startup, Home Assistant will setup the entries during the normal setup
of a component. It will first call the normal setup and then call the method
`async_setup_entry(hass, entry)` for each entry. The same method is called when
Home Assistant is running while a config entry is created.

## Config Flows

A component needs to define a Config Handler to allow the user to create config
entries for that component. A config flow will manage the creation of entries
from user input, discovery or other sources (like hassio).

When a config flow is started for a domain, the handler will be instantiated
and receives a unique id. The instance of this handler will be reused for every
interaction of the user with this flow. This makes it possible to store
instance variables on the handler.

Before instantiating the handler, Home Assistant will make sure to load all
dependencies and install the requirements of the component.

At a minimum, each config flow will have to define a version number and the
'init' step.

    @config_entries.HANDLERS.register(DOMAIN)
    class ExampleConfigFlow(config_entries.FlowHandler):

        VERSION = 1

        async def async_step_init(self, user_input=None):
            …

The 'init' step is the first step of a flow and is called when a user
starts a new flow. Each step has three different possible results: "Show Form",
"Abort" and "Create Entry".

### Show Form

This will show a form to the user to fill in. You define the current step,
a title, a description and the schema of the data that needs to be returned.

    async def async_step_init(self, user_input=None):
        # Use OrderedDict to guarantee order of the form shown to the user
        data_schema = OrderedDict()
        data_schema[vol.Required('username')] = str
        data_schema[vol.Required('password')] = str

        return self.async_show_form(
            step_id='init',
            title='Account Info',
            data_schema=vol.Schema(data_schema)
        )

After the user has filled in the form, the step method will be called again and
the user input is passed in. If the validation of the user input fails , you
can return a dictionary with errors. Each key in the dictionary refers to a
field name that contains the error. Use the key 'base' if you want to show a
generic error.

    async def async_step_init(self, user_input=None):
        errors = None
        if user_input is not None:
            # Validate user input
            if valid:
                return self.create_entry(…)

            errors['base'] = 'Unable to reach authentication server.'

        return self.async_show_form(…)

If the user input passes validation, you can again return one of the three
return values. If you want to navigate the user to the next step, return the
return value of that step:

    return await self.async_step_account()

### Abort

When the result is "Abort", a message will be shown to the user and the
configuration flow is finished.

    return self.async_abort(
        reason='This device is not supported by Home Assistant.'
    )

### Create Entry

When the result is "Create Entry", an entry will be created and stored in Home
Assistant, a success message is shown to the user and the flow is finished.

## Initializing a config flow from an external source

You might want to initialize a config flow programmatically. For example, if
we discover a device on the network that requires user interaction to finish
setup. To do so, pass a source parameter and optional user input to the init
step:

    await hass.config_entries.flow.async_init(
        'hue', source='discovery', data=discovery_info)

The config flow handler will need to add a step to support the source. The step
should follow the same return values as a normal step.

    async def async_step_discovery(info):

If the result of the step is to show a form, the user will be able to continue
the flow from the config panel.
"""

import logging
import uuid

from homeassistant import data_entry_flow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component, async_process_deps_reqs
from homeassistant.util.decorator import Registry


_LOGGER = logging.getLogger(__name__)
HANDLERS = Registry()
# Components that have config flows. In future we will auto-generate this list.
FLOWS = [
    'cast',
    'deconz',
    'homematicip_cloud',
    'hue',
    'nest',
    'sonos',
    'zone',
]


STORAGE_KEY = 'core.config_entries'
STORAGE_VERSION = 1

# Deprecated since 0.73
PATH_CONFIG = '.config_entries.json'

SAVE_DELAY = 1

ENTRY_STATE_LOADED = 'loaded'
ENTRY_STATE_SETUP_ERROR = 'setup_error'
ENTRY_STATE_NOT_LOADED = 'not_loaded'
ENTRY_STATE_FAILED_UNLOAD = 'failed_unload'

DISCOVERY_NOTIFICATION_ID = 'config_entry_discovery'
DISCOVERY_SOURCES = (
    data_entry_flow.SOURCE_DISCOVERY,
    data_entry_flow.SOURCE_IMPORT,
)

EVENT_FLOW_DISCOVERED = 'config_entry_discovered'


class ConfigEntry:
    """Hold a configuration entry."""

    __slots__ = ('entry_id', 'version', 'domain', 'title', 'data', 'source',
                 'state')

    def __init__(self, version, domain, title, data, source, entry_id=None,
                 state=ENTRY_STATE_NOT_LOADED):
        """Initialize a config entry."""
        # Unique id of the config entry
        self.entry_id = entry_id or uuid.uuid4().hex

        # Version of the configuration.
        self.version = version

        # Domain the configuration belongs to
        self.domain = domain

        # Title of the configuration
        self.title = title

        # Config data
        self.data = data

        # Source of the configuration (user, discovery, cloud)
        self.source = source

        # State of the entry (LOADED, NOT_LOADED)
        self.state = state

    async def async_setup(self, hass, *, component=None):
        """Set up an entry."""
        if component is None:
            component = getattr(hass.components, self.domain)

        try:
            result = await component.async_setup_entry(hass, self)

            if not isinstance(result, bool):
                _LOGGER.error('%s.async_config_entry did not return boolean',
                              component.DOMAIN)
                result = False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up entry %s for %s',
                              self.title, component.DOMAIN)
            result = False

        # Only store setup result as state if it was not forwarded.
        if self.domain != component.DOMAIN:
            return

        if result:
            self.state = ENTRY_STATE_LOADED
        else:
            self.state = ENTRY_STATE_SETUP_ERROR

    async def async_unload(self, hass, *, component=None):
        """Unload an entry.

        Returns if unload is possible and was successful.
        """
        if component is None:
            component = getattr(hass.components, self.domain)

        supports_unload = hasattr(component, 'async_unload_entry')

        if not supports_unload:
            return False

        try:
            result = await component.async_unload_entry(hass, self)

            if not isinstance(result, bool):
                _LOGGER.error('%s.async_unload_entry did not return boolean',
                              component.DOMAIN)
                result = False

            return result
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error unloading entry %s for %s',
                              self.title, component.DOMAIN)
            self.state = ENTRY_STATE_FAILED_UNLOAD
            return False

    def as_dict(self):
        """Return dictionary version of this entry."""
        return {
            'entry_id': self.entry_id,
            'version': self.version,
            'domain': self.domain,
            'title': self.title,
            'data': self.data,
            'source': self.source,
        }


class ConfigError(HomeAssistantError):
    """Error while configuring an account."""


class UnknownEntry(ConfigError):
    """Unknown entry specified."""


class ConfigEntries:
    """Manage the configuration entries.

    An instance of this object is available via `hass.config_entries`.
    """

    def __init__(self, hass, hass_config):
        """Initialize the entry manager."""
        self.hass = hass
        self.flow = data_entry_flow.FlowManager(
            hass, self._async_create_flow, self._async_finish_flow)
        self._hass_config = hass_config
        self._entries = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_domains(self):
        """Return domains for which we have entries."""
        seen = set()
        result = []

        for entry in self._entries:
            if entry.domain not in seen:
                seen.add(entry.domain)
                result.append(entry.domain)

        return result

    @callback
    def async_entries(self, domain=None):
        """Return all entries or entries for a specific domain."""
        if domain is None:
            return list(self._entries)
        return [entry for entry in self._entries if entry.domain == domain]

    async def async_remove(self, entry_id):
        """Remove an entry."""
        found = None
        for index, entry in enumerate(self._entries):
            if entry.entry_id == entry_id:
                found = index
                break

        if found is None:
            raise UnknownEntry

        entry = self._entries.pop(found)
        await self._async_schedule_save()

        unloaded = await entry.async_unload(self.hass)

        return {
            'require_restart': not unloaded
        }

    async def async_load(self):
        """Handle loading the config."""
        # Migrating for config entries stored before 0.73
        config = await self.hass.helpers.storage.async_migrator(
            self.hass.config.path(PATH_CONFIG), self._store,
            old_conf_migrate_func=_old_conf_migrator
        )

        if config is None:
            self._entries = []
            return

        self._entries = [ConfigEntry(**entry) for entry in config['entries']]

    async def async_forward_entry_setup(self, entry, component):
        """Forward the setup of an entry to a different component.

        By default an entry is setup with the component it belongs to. If that
        component also has related platforms, the component will have to
        forward the entry to be setup by that component.

        You don't want to await this coroutine if it is called as part of the
        setup of a component, because it can cause a deadlock.
        """
        # Setup Component if not set up yet
        if component not in self.hass.config.components:
            result = await async_setup_component(
                self.hass, component, self._hass_config)

            if not result:
                return False

        await entry.async_setup(
            self.hass, component=getattr(self.hass.components, component))

    async def async_forward_entry_unload(self, entry, component):
        """Forward the unloading of an entry to a different component."""
        # It was never loaded.
        if component not in self.hass.config.components:
            return True

        return await entry.async_unload(
            self.hass, component=getattr(self.hass.components, component))

    async def _async_finish_flow(self, result):
        """Finish a config flow and add an entry."""
        # If no discovery config entries in progress, remove notification.
        if not any(ent['source'] in DISCOVERY_SOURCES for ent
                   in self.hass.config_entries.flow.async_progress()):
            self.hass.components.persistent_notification.async_dismiss(
                DISCOVERY_NOTIFICATION_ID)

        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return None

        entry = ConfigEntry(
            version=result['version'],
            domain=result['handler'],
            title=result['title'],
            data=result['data'],
            source=result['source'],
        )
        self._entries.append(entry)
        await self._async_schedule_save()

        # Setup entry
        if entry.domain in self.hass.config.components:
            # Component already set up, just need to call setup_entry
            await entry.async_setup(self.hass)
        else:
            # Setting up component will also load the entries
            await async_setup_component(
                self.hass, entry.domain, self._hass_config)

        # Return Entry if they not from a discovery request
        if result['source'] not in DISCOVERY_SOURCES:
            return entry

        return entry

    async def _async_create_flow(self, handler, *, source, data):
        """Create a flow for specified handler.

        Handler key is the domain of the component that we want to setup.
        """
        component = getattr(self.hass.components, handler)
        handler = HANDLERS.get(handler)

        if handler is None:
            raise data_entry_flow.UnknownHandler

        # Make sure requirements and dependencies of component are resolved
        await async_process_deps_reqs(
            self.hass, self._hass_config, handler, component)

        # Create notification.
        if source in DISCOVERY_SOURCES:
            self.hass.bus.async_fire(EVENT_FLOW_DISCOVERED)
            self.hass.components.persistent_notification.async_create(
                title='New devices discovered',
                message=("We have discovered new devices on your network. "
                         "[Check it out](/config/integrations)"),
                notification_id=DISCOVERY_NOTIFICATION_ID
            )

        return handler()

    async def _async_schedule_save(self):
        """Save the entity registry to a file."""
        data = {
            'entries': [entry.as_dict() for entry in self._entries]
        }
        await self._store.async_save(data, delay=SAVE_DELAY)


async def _old_conf_migrator(old_config):
    """Migrate the pre-0.73 config format to the latest version."""
    return {'entries': old_config}
