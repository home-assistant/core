"""JSON utility functions."""
from collections import deque
import json
import logging
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional, Type, Union

from homeassistant.core import Event, State
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class SerializationError(HomeAssistantError):
    """Error serializing the data to JSON."""


class WriteError(HomeAssistantError):
    """Error writing the data."""


def load_json(
    filename: str, default: Union[List, Dict, None] = None
) -> Union[List, Dict]:
    """Load JSON data from a file and return as dict or list.

    Defaults to returning empty dict if file is not found.
    """
    try:
        with open(filename, encoding="utf-8") as fdesc:
            return json.loads(fdesc.read())  # type: ignore
    except FileNotFoundError:
        # This is not a fatal error
        _LOGGER.debug("JSON file not found: %s", filename)
    except ValueError as error:
        _LOGGER.exception("Could not parse JSON content: %s", filename)
        raise HomeAssistantError(error)
    except OSError as error:
        _LOGGER.exception("JSON file reading failed: %s", filename)
        raise HomeAssistantError(error)
    return {} if default is None else default


def save_json(
    filename: str,
    data: Union[List, Dict],
    private: bool = False,
    *,
    encoder: Optional[Type[json.JSONEncoder]] = None,
) -> None:
    """Save JSON data to a file.

    Returns True on success.
    """
    try:
        json_data = json.dumps(data, indent=4, cls=encoder)
    except TypeError:
        msg = f"Failed to serialize to JSON: {filename}. Bad data at {format_unserializable_data(find_paths_unserializable_data(data))}"
        _LOGGER.error(msg)
        raise SerializationError(msg)

    tmp_filename = ""
    tmp_path = os.path.split(filename)[0]
    try:
        # Modern versions of Python tempfile create this file with mode 0o600
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=tmp_path, delete=False
        ) as fdesc:
            fdesc.write(json_data)
            tmp_filename = fdesc.name
        if not private:
            os.chmod(tmp_filename, 0o644)
        os.replace(tmp_filename, filename)
    except OSError as error:
        _LOGGER.exception("Saving JSON file failed: %s", filename)
        raise WriteError(error)
    finally:
        if os.path.exists(tmp_filename):
            try:
                os.remove(tmp_filename)
            except OSError as err:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error("JSON replacement cleanup failed: %s", err)


def format_unserializable_data(data: Dict[str, Any]) -> str:
    """Format output of find_paths in a friendly way.

    Format is comma separated: <path>=<value>(<type>)
    """
    return ", ".join(f"{path}={value}({type(value)}" for path, value in data.items())


def find_paths_unserializable_data(
    bad_data: Any, *, dump: Callable[[Any], str] = json.dumps
) -> Dict[str, Any]:
    """Find the paths to unserializable data.

    This method is slow! Only use for error handling.
    """
    to_process = deque([(bad_data, "$")])
    invalid = {}

    while to_process:
        obj, obj_path = to_process.popleft()

        try:
            dump(obj)
            continue
        except (ValueError, TypeError):
            pass

        # We convert states and events to dict so we can find bad data inside it
        if isinstance(obj, State):
            obj_path += f"(state: {obj.entity_id})"
            obj = obj.as_dict()
        elif isinstance(obj, Event):
            obj_path += f"(event: {obj.event_type})"
            obj = obj.as_dict()

        if isinstance(obj, dict):
            for key, value in obj.items():
                try:
                    # Is key valid?
                    dump({key: None})
                except TypeError:
                    invalid[f"{obj_path}<key: {key}>"] = key
                else:
                    # Process value
                    to_process.append((value, f"{obj_path}.{key}"))
        elif isinstance(obj, list):
            for idx, value in enumerate(obj):
                to_process.append((value, f"{obj_path}[{idx}]"))
        else:
            invalid[obj_path] = obj

    return invalid
