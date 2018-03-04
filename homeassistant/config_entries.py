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
    class ExampleConfigFlow(config_entries.ConfigFlowHandler):

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
import os
import uuid

from .core import callback
from .exceptions import HomeAssistantError
from .setup import async_setup_component, async_process_deps_reqs
from .util.json import load_json, save_json
from .util.decorator import Registry


_LOGGER = logging.getLogger(__name__)
HANDLERS = Registry()
# Components that have config flows. In future we will auto-generate this list.
FLOWS = [
    'config_entry_example',
    'hue',
]

SOURCE_USER = 'user'
SOURCE_DISCOVERY = 'discovery'

PATH_CONFIG = '.config_entries.json'

SAVE_DELAY = 1

RESULT_TYPE_FORM = 'form'
RESULT_TYPE_CREATE_ENTRY = 'create_entry'
RESULT_TYPE_ABORT = 'abort'

ENTRY_STATE_LOADED = 'loaded'
ENTRY_STATE_SETUP_ERROR = 'setup_error'
ENTRY_STATE_NOT_LOADED = 'not_loaded'
ENTRY_STATE_FAILED_UNLOAD = 'failed_unload'


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
                              self.domain)
                result = False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up entry %s for %s',
                              self.title, self.domain)
            result = False

        if result:
            self.state = ENTRY_STATE_LOADED
        else:
            self.state = ENTRY_STATE_SETUP_ERROR

    async def async_unload(self, hass):
        """Unload an entry.

        Returns if unload is possible and was successful.
        """
        component = getattr(hass.components, self.domain)

        supports_unload = hasattr(component, 'async_unload_entry')

        if not supports_unload:
            return False

        try:
            result = await component.async_unload_entry(hass, self)

            if not isinstance(result, bool):
                _LOGGER.error('%s.async_unload_entry did not return boolean',
                              self.domain)
                result = False

            return result
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error unloading entry %s for %s',
                              self.title, self.domain)
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


class UnknownHandler(ConfigError):
    """Unknown handler specified."""


class UnknownFlow(ConfigError):
    """Uknown flow specified."""


class UnknownStep(ConfigError):
    """Unknown step specified."""


class ConfigEntries:
    """Manage the configuration entries.

    An instance of this object is available via `hass.config_entries`.
    """

    def __init__(self, hass, hass_config):
        """Initialize the entry manager."""
        self.hass = hass
        self.flow = FlowManager(hass, hass_config, self._async_add_entry)
        self._hass_config = hass_config
        self._entries = None
        self._sched_save = None

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
        self._async_schedule_save()

        unloaded = await entry.async_unload(self.hass)

        return {
            'require_restart': not unloaded
        }

    async def async_load(self):
        """Load the config."""
        path = self.hass.config.path(PATH_CONFIG)
        if not os.path.isfile(path):
            self._entries = []
            return

        entries = await self.hass.async_add_job(load_json, path)
        self._entries = [ConfigEntry(**entry) for entry in entries]

    async def _async_add_entry(self, entry):
        """Add an entry."""
        self._entries.append(entry)
        self._async_schedule_save()

        # Setup entry
        if entry.domain in self.hass.config.components:
            # Component already set up, just need to call setup_entry
            await entry.async_setup(self.hass)
        else:
            # Setting up component will also load the entries
            await async_setup_component(
                self.hass, entry.domain, self._hass_config)

    @callback
    def _async_schedule_save(self):
        """Schedule saving the entity registry."""
        if self._sched_save is not None:
            self._sched_save.cancel()

        self._sched_save = self.hass.loop.call_later(
            SAVE_DELAY, self.hass.async_add_job, self._async_save
        )

    async def _async_save(self):
        """Save the entity registry to a file."""
        self._sched_save = None
        data = [entry.as_dict() for entry in self._entries]

        await self.hass.async_add_job(
            save_json, self.hass.config.path(PATH_CONFIG), data)


class FlowManager:
    """Manage all the config flows that are in progress."""

    def __init__(self, hass, hass_config, async_add_entry):
        """Initialize the flow manager."""
        self.hass = hass
        self._hass_config = hass_config
        self._progress = {}
        self._async_add_entry = async_add_entry

    @callback
    def async_progress(self):
        """Return the flows in progress."""
        return [{
            'flow_id': flow.flow_id,
            'domain': flow.domain,
            'source': flow.source,
        } for flow in self._progress.values()]

    async def async_init(self, domain, *, source=SOURCE_USER, data=None):
        """Start a configuration flow."""
        handler = HANDLERS.get(domain)

        if handler is None:
            # This will load the component and thus register the handler
            component = getattr(self.hass.components, domain)
            handler = HANDLERS.get(domain)

            if handler is None:
                raise self.hass.helpers.UnknownHandler

            # Make sure requirements and dependencies of component are resolved
            await async_process_deps_reqs(
                self.hass, self._hass_config, domain, component)

        flow_id = uuid.uuid4().hex
        flow = self._progress[flow_id] = handler()
        flow.hass = self.hass
        flow.domain = domain
        flow.flow_id = flow_id
        flow.source = source

        if source == SOURCE_USER:
            step = 'init'
        else:
            step = source

        return await self._async_handle_step(flow, step, data)

    async def async_configure(self, flow_id, user_input=None):
        """Start or continue a configuration flow."""
        flow = self._progress.get(flow_id)

        if flow is None:
            raise UnknownFlow

        step_id, data_schema = flow.cur_step

        if data_schema is not None and user_input is not None:
            user_input = data_schema(user_input)

        return await self._async_handle_step(
            flow, step_id, user_input)

    @callback
    def async_abort(self, flow_id):
        """Abort a flow."""
        if self._progress.pop(flow_id, None) is None:
            raise UnknownFlow

    async def _async_handle_step(self, flow, step_id, user_input):
        """Handle a step of a flow."""
        method = "async_step_{}".format(step_id)

        if not hasattr(flow, method):
            self._progress.pop(flow.flow_id)
            raise UnknownStep("Handler {} doesn't support step {}".format(
                flow.__class__.__name__, step_id))

        result = await getattr(flow, method)(user_input)

        if result['type'] not in (RESULT_TYPE_FORM, RESULT_TYPE_CREATE_ENTRY,
                                  RESULT_TYPE_ABORT):
            raise ValueError(
                'Handler returned incorrect type: {}'.format(result['type']))

        if result['type'] == RESULT_TYPE_FORM:
            flow.cur_step = (result.pop('step_id'), result['data_schema'])
            return result

        # Abort and Success results both finish the flow
        self._progress.pop(flow.flow_id)

        if result['type'] == RESULT_TYPE_ABORT:
            return result

        entry = ConfigEntry(
            version=flow.VERSION,
            domain=flow.domain,
            title=result['title'],
            data=result.pop('data'),
            source=flow.source
        )
        await self._async_add_entry(entry)
        return result


class ConfigFlowHandler:
    """Handle the configuration flow of a component."""

    # Set by flow manager
    flow_id = None
    hass = None
    source = SOURCE_USER
    cur_step = None

    # Set by dev
    # VERSION

    @callback
    def async_show_form(self, *, title, step_id, description=None,
                        data_schema=None, errors=None):
        """Return the definition of a form to gather user input."""
        return {
            'type': RESULT_TYPE_FORM,
            'flow_id': self.flow_id,
            'title': title,
            'step_id': step_id,
            'description': description,
            'data_schema': data_schema,
            'errors': errors,
        }

    @callback
    def async_create_entry(self, *, title, data):
        """Finish config flow and create a config entry."""
        return {
            'type': RESULT_TYPE_CREATE_ENTRY,
            'flow_id': self.flow_id,
            'title': title,
            'data': data,
        }

    @callback
    def async_abort(self, *, reason):
        """Abort the config flow."""
        return {
            'type': RESULT_TYPE_ABORT,
            'flow_id': self.flow_id,
            'reason': reason
        }
