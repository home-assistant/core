"""JSON utility functions."""
import logging
from typing import Union, List, Dict

import json

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

_UNDEFINED = object()


def load_json(filename: str, default: Union[List, Dict] = _UNDEFINED) \
        -> Union[List, Dict]:
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
    return {} if default is _UNDEFINED else default


def save_json(filename: str, data: Union[List, Dict]):
    """Save JSON data to a file.

    Returns True on success.
    """
    try:
        data = json.dumps(data, sort_keys=True, indent=4)
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
