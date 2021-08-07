"""
Support to allow pieces of code to request configuration from the user.

Initiate a request by calling the `request_config` method with a callback.
This will return a request id that has to be used for future calls.
A callback has to be provided to `request_config` which will be called when
the user has submitted configuration information.
"""
from contextlib import suppress
import functools as ft

from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    EVENT_TIME_CHANGED,
)
from homeassistant.core import Event, callback as async_callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe

_KEY_INSTANCE = "configurator"

DATA_REQUESTS = "configurator_requests"

ATTR_CONFIGURE_ID = "configure_id"
ATTR_DESCRIPTION = "description"
ATTR_DESCRIPTION_IMAGE = "description_image"
ATTR_ERRORS = "errors"
ATTR_FIELDS = "fields"
ATTR_LINK_NAME = "link_name"
ATTR_LINK_URL = "link_url"
ATTR_SUBMIT_CAPTION = "submit_caption"

DOMAIN = "configurator"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SERVICE_CONFIGURE = "configure"
STATE_CONFIGURE = "configure"
STATE_CONFIGURED = "configured"


@bind_hass
@async_callback
def async_request_config(
    hass,
    name,
    callback=None,
    description=None,
    description_image=None,
    submit_caption=None,
    fields=None,
    link_name=None,
    link_url=None,
    entity_picture=None,
):
    """Create a new request for configuration.

    Will return an ID to be used for sequent calls.
    """
    if link_name is not None and link_url is not None:
        description += f"\n\n[{link_name}]({link_url})"

    if description_image is not None:
        description += f"\n\n![Description image]({description_image})"

    instance = hass.data.get(_KEY_INSTANCE)

    if instance is None:
        instance = hass.data[_KEY_INSTANCE] = Configurator(hass)

    request_id = instance.async_request_config(
        name, callback, description, submit_caption, fields, entity_picture
    )

    if DATA_REQUESTS not in hass.data:
        hass.data[DATA_REQUESTS] = {}

    hass.data[DATA_REQUESTS][request_id] = instance

    return request_id


@bind_hass
def request_config(hass, *args, **kwargs):
    """Create a new request for configuration.

    Will return an ID to be used for sequent calls.
    """
    return run_callback_threadsafe(
        hass.loop, ft.partial(async_request_config, hass, *args, **kwargs)
    ).result()


@bind_hass
@async_callback
def async_notify_errors(hass, request_id, error):
    """Add errors to a config request."""
    with suppress(KeyError):  # If request_id does not exist
        hass.data[DATA_REQUESTS][request_id].async_notify_errors(request_id, error)


@bind_hass
def notify_errors(hass, request_id, error):
    """Add errors to a config request."""
    return run_callback_threadsafe(
        hass.loop, async_notify_errors, hass, request_id, error
    ).result()


@bind_hass
@async_callback
def async_request_done(hass, request_id):
    """Mark a configuration request as done."""
    with suppress(KeyError):  # If request_id does not exist
        hass.data[DATA_REQUESTS].pop(request_id).async_request_done(request_id)


@bind_hass
def request_done(hass, request_id):
    """Mark a configuration request as done."""
    return run_callback_threadsafe(
        hass.loop, async_request_done, hass, request_id
    ).result()


async def async_setup(hass, config):
    """Set up the configurator component."""
    return True


class Configurator:
    """The class to keep track of current configuration requests."""

    def __init__(self, hass):
        """Initialize the configurator."""
        self.hass = hass
        self._cur_id = 0
        self._requests = {}
        hass.services.async_register(
            DOMAIN, SERVICE_CONFIGURE, self.async_handle_service_call
        )

    @async_callback
    def async_request_config(
        self, name, callback, description, submit_caption, fields, entity_picture
    ):
        """Set up a request for configuration."""
        entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, name, hass=self.hass)

        if fields is None:
            fields = []

        request_id = self._generate_unique_id()

        self._requests[request_id] = (entity_id, fields, callback)

        data = {
            ATTR_CONFIGURE_ID: request_id,
            ATTR_FIELDS: fields,
            ATTR_FRIENDLY_NAME: name,
            ATTR_ENTITY_PICTURE: entity_picture,
        }

        data.update(
            {
                key: value
                for key, value in (
                    (ATTR_DESCRIPTION, description),
                    (ATTR_SUBMIT_CAPTION, submit_caption),
                )
                if value is not None
            }
        )

        self.hass.states.async_set(entity_id, STATE_CONFIGURE, data)

        return request_id

    @async_callback
    def async_notify_errors(self, request_id, error):
        """Update the state with errors."""
        if not self._validate_request_id(request_id):
            return

        entity_id = self._requests[request_id][0]

        state = self.hass.states.get(entity_id)

        new_data = dict(state.attributes)
        new_data[ATTR_ERRORS] = error

        self.hass.states.async_set(entity_id, STATE_CONFIGURE, new_data)

    @async_callback
    def async_request_done(self, request_id):
        """Remove the configuration request."""
        if not self._validate_request_id(request_id):
            return

        entity_id = self._requests.pop(request_id)[0]

        # If we remove the state right away, it will not be included with
        # the result of the service call (current design limitation).
        # Instead, we will set it to configured to give as feedback but delete
        # it shortly after so that it is deleted when the client updates.
        self.hass.states.async_set(entity_id, STATE_CONFIGURED)

        def deferred_remove(event: Event):
            """Remove the request state."""
            self.hass.states.async_remove(entity_id, context=event.context)

        self.hass.bus.async_listen_once(EVENT_TIME_CHANGED, deferred_remove)

    async def async_handle_service_call(self, call):
        """Handle a configure service call."""
        request_id = call.data.get(ATTR_CONFIGURE_ID)

        if not self._validate_request_id(request_id):
            return

        # pylint: disable=unused-variable
        entity_id, fields, callback = self._requests[request_id]

        # field validation goes here?
        if callback:
            await self.hass.async_add_job(callback, call.data.get(ATTR_FIELDS, {}))

    def _generate_unique_id(self):
        """Generate a unique configurator ID."""
        self._cur_id += 1
        return f"{id(self)}-{self._cur_id}"

    def _validate_request_id(self, request_id):
        """Validate that the request belongs to this instance."""
        return request_id in self._requests
