"""JSON utility functions."""
import logging
from typing import Union, List, Dict, Optional

import json
import os
import tempfile

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
              private: bool = False, *,
              encoder: Optional[json.JSONEncoder] = None) -> None:
    """Save JSON data to a file.

    Returns True on success.
    """
    tmp_filename = ""
    tmp_path = os.path.split(filename)[0]
    try:
        json_data = json.dumps(data, sort_keys=True, indent=4, cls=encoder)
        # Modern versions of Python tempfile create this file with mode 0o600
        with tempfile.NamedTemporaryFile(mode="w", encoding='utf-8',
                                         dir=tmp_path, delete=False) as fdesc:
            fdesc.write(json_data)
            tmp_filename = fdesc.name
        if not private:
            os.chmod(tmp_filename, 0o644)
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
