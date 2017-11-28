"""JSON utility functions."""
import logging
from typing import Union, List, Dict

import json

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


def load_json(filename: str) -> Union[List, Dict]:
    """Load JSON data from a file and return as dict or list.

    Defaults to returning empty dict if file is not found.
    """
    try:
        with open(filename, encoding='utf-8') as fdesc:
            return json.loads(fdesc.read())
    except FileNotFoundError:
        # This is not a fatal error
        _LOGGER.debug('JSON file not found: %s', filename)
    except ValueError as error:
        _LOGGER.exception('Could not parse JSON content: %s', filename)
        raise HomeAssistantError(error)
    except OSError as error:
        _LOGGER.exception('JSON file reading failed: %s', filename)
        raise HomeAssistantError(error)
    return {}  # (also evaluates to False)


def save_json(filename: str, config: Union[List, Dict]):
    """Save JSON data to a file.

    Returns True on success.
    """
    try:
        data = json.dumps(config, sort_keys=True, indent=4,
                          cls=JSONBytesDecoder)
        with open(filename, 'w', encoding='utf-8') as fdesc:
            fdesc.write(data)
            return True
    except TypeError as error:
        _LOGGER.exception('Failed to serialize to JSON: %s',
                          filename)
        raise HomeAssistantError(error)
    except OSError as error:
        _LOGGER.exception('Saving JSON file failed: %s',
                          filename)
        raise HomeAssistantError(error)
    return False


class JSONBytesDecoder(json.JSONEncoder):
    """JSONEncoder to decode bytes objects to unicode."""

    # pylint: disable=method-hidden
    def default(self, obj):
        """Decode object if it's a bytes object, else defer to base class."""
        if isinstance(obj, bytes):
            return obj.decode()
        return json.JSONEncoder.default(self, obj)
