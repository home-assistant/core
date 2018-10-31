"""JSON utility functions."""
import logging
from typing import Union, List, Dict

import json
import os
from os import O_WRONLY, O_CREAT, O_TRUNC

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class SerializationError(HomeAssistantError):
    """Error serializing the data to JSON."""


class WriteError(HomeAssistantError):
    """Error writing the data."""


def load_json(filename: str, default: Union[List, Dict, None] = None) \
        -> Union[List, Dict]:
    """Load JSON data from a file and return as dict or list.

    Defaults to returning empty dict if file is not found.
    """
    try:
        with open(filename, encoding='utf-8') as fdesc:
            return json.loads(fdesc.read())  # type: ignore
    except FileNotFoundError:
        # This is not a fatal error
        _LOGGER.debug('JSON file not found: %s', filename)
    except ValueError as error:
        _LOGGER.exception('Could not parse JSON content: %s', filename)
        raise HomeAssistantError(error)
    except OSError as error:
        _LOGGER.exception('JSON file reading failed: %s', filename)
        raise HomeAssistantError(error)
    return {} if default is None else default


def save_json(filename: str, data: Union[List, Dict],
              private: bool = False) -> None:
    """Save JSON data to a file.

    Returns True on success.
    """
    tmp_filename = filename + "__TEMP__"
    try:
        json_data = json.dumps(data, sort_keys=True, indent=4)
        mode = 0o600 if private else 0o644
        with open(os.open(tmp_filename, O_WRONLY | O_CREAT | O_TRUNC, mode),
                  'w', encoding='utf-8') as fdesc:
            fdesc.write(json_data)
        os.replace(tmp_filename, filename)
    except TypeError as error:
        _LOGGER.exception('Failed to serialize to JSON: %s',
                          filename)
        raise SerializationError(error)
    except OSError as error:
        _LOGGER.exception('Saving JSON file failed: %s',
                          filename)
        raise WriteError(error)
    finally:
        if os.path.exists(tmp_filename):
            try:
                os.remove(tmp_filename)
            except OSError as err:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error("JSON replacement cleanup failed: %s", err)
