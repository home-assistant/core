import logging

from homeassistant.helpers import generate_entity_id
from homeassistant.const import EVENT_TIME_CHANGED

DOMAIN = "configurator"
DEPENDENCIES = []
ENTITY_ID_FORMAT = DOMAIN + ".{}"

SERVICE_CONFIGURE = "configure"

STATE_CONFIGURE = "configure"
STATE_CONFIGURED = "configured"

ATTR_CONFIGURE_ID = "configure_id"
ATTR_DESCRIPTION = "description"
ATTR_DESCRIPTION_IMAGE = "description_image"
ATTR_SUBMIT_CAPTION = "submit_caption"
ATTR_FIELDS = "fields"
ATTR_ERRORS = "errors"

_INSTANCES = {}
_LOGGER = logging.getLogger(__name__)


def request_config(
        hass, name, callback, description=None, description_image=None,
        submit_caption=None, fields=None):
    """ Create a new request for config.
    Will return an ID to be used for sequent calls. """

    return _get_instance(hass).request_config(
        name, callback,
        description, description_image, submit_caption, fields)


def notify_errors(hass, request_id, error):
    _get_instance(hass).notify_errors(request_id, error)


def request_done(hass, request_id):
    _get_instance(hass).request_done(request_id)


def setup(hass, config):
    return True


def _get_instance(hass):
    """ Get an instance per hass object. """
    try:
        return _INSTANCES[hass]
    except KeyError:
        print("Creating instance")
        _INSTANCES[hass] = Configurator(hass)

        if DOMAIN not in hass.components:
            hass.components.append(DOMAIN)

        return _INSTANCES[hass]


class Configurator(object):
    def __init__(self, hass):
        self.hass = hass
        self._cur_id = 0
        self._requests = {}
        hass.services.register(
            DOMAIN, SERVICE_CONFIGURE, self.handle_service_call)

    def request_config(
            self, name, callback,
            description, description_image, submit_caption, fields):
        """ Setup a request for configuration. """

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
            ] if value is not None
        })

        self.hass.states.set(entity_id, STATE_CONFIGURE, data)

        return request_id

    def notify_errors(self, request_id, error):
        """ Update the state with errors. """
        if not self._validate_request_id(request_id):
            return

        entity_id = self._requests[request_id][0]

        state = self.hass.states.get(entity_id)

        new_data = state.attributes
        new_data[ATTR_ERRORS] = error

        self.hass.states.set(entity_id, STATE_CONFIGURE, new_data)

    def request_done(self, request_id):
        """ Remove the config request. """
        if not self._validate_request_id(request_id):
            return

        entity_id = self._requests.pop(request_id)[0]

        # If we remove the state right away, it will not be passed down
        # with the service request (limitation current design).
        # Instead we will set it to configured right away and remove it soon.
        def deferred_remove(event):
            self.hass.states.remove(entity_id)

        self.hass.bus.listen_once(EVENT_TIME_CHANGED, deferred_remove)

        self.hass.states.set(entity_id, STATE_CONFIGURED)

    def handle_service_call(self, call):
        request_id = call.data.get(ATTR_CONFIGURE_ID)

        if not self._validate_request_id(request_id):
            return

        entity_id, fields, callback = self._requests[request_id]

        # TODO field validation?

        callback(call.data.get(ATTR_FIELDS, {}))

    def _generate_unique_id(self):
        """ Generates a unique configurator id. """
        self._cur_id += 1
        return "{}-{}".format(id(self), self._cur_id)

    def _validate_request_id(self, request_id):
        if request_id not in self._requests:
            _LOGGER.error("Invalid configure id received: %s", request_id)
            return False

        return True
