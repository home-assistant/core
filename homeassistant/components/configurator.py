"""
Support to allow pieces of code to request configuration from the user.

Initiate a request by calling the `request_config` method with a callback.
This will return a request id that has to be used for future calls.
A callback has to be provided to `request_config` which will be called when
the user has submitted configuration information.
"""
import logging

from homeassistant.const import EVENT_TIME_CHANGED
from homeassistant.helpers.entity import generate_entity_id

DOMAIN = "configurator"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

SERVICE_CONFIGURE = "configure"

STATE_CONFIGURE = "configure"
STATE_CONFIGURED = "configured"

ATTR_LINK_NAME = "link_name"
ATTR_LINK_URL = "link_url"
ATTR_CONFIGURE_ID = "configure_id"
ATTR_DESCRIPTION = "description"
ATTR_DESCRIPTION_IMAGE = "description_image"
ATTR_SUBMIT_CAPTION = "submit_caption"
ATTR_FIELDS = "fields"
ATTR_ERRORS = "errors"

_REQUESTS = {}
_INSTANCES = {}
_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-arguments
def request_config(
        hass, name, callback, description=None, description_image=None,
        submit_caption=None, fields=None, link_name=None, link_url=None):
    """Create a new request for configuration.

    Will return an ID to be used for sequent calls.
    """
    instance = _get_instance(hass)

    request_id = instance.request_config(
        name, callback,
        description, description_image, submit_caption,
        fields, link_name, link_url)

    _REQUESTS[request_id] = instance

    return request_id


def notify_errors(request_id, error):
    """Add errors to a config request."""
    try:
        _REQUESTS[request_id].notify_errors(request_id, error)
    except KeyError:
        # If request_id does not exist
        pass


def request_done(request_id):
    """Mark a configuration request as done."""
    try:
        _REQUESTS.pop(request_id).request_done(request_id)
    except KeyError:
        # If request_id does not exist
        pass


def setup(hass, config):
    """Setup the configurator component."""
    return True


def _get_instance(hass):
    """Get an instance per hass object."""
    try:
        return _INSTANCES[hass]
    except KeyError:
        _INSTANCES[hass] = Configurator(hass)

        if DOMAIN not in hass.config.components:
            hass.config.components.append(DOMAIN)

        return _INSTANCES[hass]


class Configurator(object):
    """The class to keep track of current configuration requests."""

    def __init__(self, hass):
        """Initialize the configurator."""
        self.hass = hass
        self._cur_id = 0
        self._requests = {}
        hass.services.register(
            DOMAIN, SERVICE_CONFIGURE, self.handle_service_call)

    # pylint: disable=too-many-arguments
    def request_config(
            self, name, callback,
            description, description_image, submit_caption,
            fields, link_name, link_url):
        """Setup a request for configuration."""
        entity_id = generate_entity_id(ENTITY_ID_FORMAT, name, hass=self.hass)

        if fields is None:
            fields = []

        request_id = self._generate_unique_id()

        self._requests[request_id] = (entity_id, fields, callback)

        data = {
            ATTR_CONFIGURE_ID: request_id,
            ATTR_FIELDS: fields,
        }

        data.update({
            key: value for key, value in [
                (ATTR_DESCRIPTION, description),
                (ATTR_DESCRIPTION_IMAGE, description_image),
                (ATTR_SUBMIT_CAPTION, submit_caption),
                (ATTR_LINK_NAME, link_name),
                (ATTR_LINK_URL, link_url),
            ] if value is not None
        })

        self.hass.states.set(entity_id, STATE_CONFIGURE, data)

        return request_id

    def notify_errors(self, request_id, error):
        """Update the state with errors."""
        if not self._validate_request_id(request_id):
            return

        entity_id = self._requests[request_id][0]

        state = self.hass.states.get(entity_id)

        new_data = dict(state.attributes)
        new_data[ATTR_ERRORS] = error

        self.hass.states.set(entity_id, STATE_CONFIGURE, new_data)

    def request_done(self, request_id):
        """Remove the configuration request."""
        if not self._validate_request_id(request_id):
            return

        entity_id = self._requests.pop(request_id)[0]

        # If we remove the state right away, it will not be included with
        # the result fo the service call (current design limitation).
        # Instead, we will set it to configured to give as feedback but delete
        # it shortly after so that it is deleted when the client updates.
        self.hass.states.set(entity_id, STATE_CONFIGURED)

        def deferred_remove(event):
            """Remove the request state."""
            self.hass.states.remove(entity_id)

        self.hass.bus.listen_once(EVENT_TIME_CHANGED, deferred_remove)

    def handle_service_call(self, call):
        """Handle a configure service call."""
        request_id = call.data.get(ATTR_CONFIGURE_ID)

        if not self._validate_request_id(request_id):
            return

        # pylint: disable=unused-variable
        entity_id, fields, callback = self._requests[request_id]

        # field validation goes here?

        callback(call.data.get(ATTR_FIELDS, {}))

    def _generate_unique_id(self):
        """Generate a unique configurator ID."""
        self._cur_id += 1
        return "{}-{}".format(id(self), self._cur_id)

    def _validate_request_id(self, request_id):
        """Validate that the request belongs to this instance."""
        return request_id in self._requests
