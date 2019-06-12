"""Decorator for view methods to help with data validation."""
from functools import wraps
import logging

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


class RequestDataValidator:
    """Decorator that will validate the incoming data.

    Takes in a voluptuous schema and adds 'post_data' as
    keyword argument to the function call.

    Will return a 400 if no JSON provided or doesn't match schema.
    """

    def __init__(self, schema, allow_empty=False):
        """Initialize the decorator."""
        self._schema = schema
        self._allow_empty = allow_empty

    def __call__(self, method):
        """Decorate a function."""
        @wraps(method)
        async def wrapper(view, request, *args, **kwargs):
            """Wrap a request handler with data validation."""
            data = None
            try:
                data = await request.json()
            except ValueError:
                if not self._allow_empty or \
                   (await request.content.read()) != b'':
                    _LOGGER.error('Invalid JSON received.')
                    return view.json_message('Invalid JSON.', 400)
                data = {}

            try:
                kwargs['data'] = self._schema(data)
            except vol.Invalid as err:
                _LOGGER.error('Data does not match schema: %s', err)
                return view.json_message(
                    'Message format incorrect: {}'.format(err), 400)

            result = await method(view, request, *args, **kwargs)
            return result

        return wrapper
