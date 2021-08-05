"""Component to allow running Python scripts."""
import datetime
import glob
import logging
import os
import time

from RestrictedPython import (
    compile_restricted_exec,
    limited_builtins,
    safe_builtins,
    utility_builtins,
)
from RestrictedPython.Eval import default_guarded_getitem
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
)
import voluptuous as vol

from homeassistant.const import CONF_DESCRIPTION, CONF_NAME, SERVICE_RELOAD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.loader import bind_hass
from homeassistant.util import raise_if_invalid_filename
import homeassistant.util.dt as dt_util
from homeassistant.util.yaml.loader import load_yaml

_LOGGER = logging.getLogger(__name__)

DOMAIN = "python_script"

FOLDER = "python_scripts"

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema(dict)}, extra=vol.ALLOW_EXTRA)

ALLOWED_HASS = {"bus", "services", "states"}
ALLOWED_EVENTBUS = {"fire"}
ALLOWED_STATEMACHINE = {
    "entity_ids",
    "all",
    "get",
    "is_state",
    "is_state_attr",
    "remove",
    "set",
}
ALLOWED_SERVICEREGISTRY = {"services", "has_service", "call"}
ALLOWED_TIME = {
    "sleep",
    "strftime",
    "strptime",
    "gmtime",
    "localtime",
    "ctime",
    "time",
    "mktime",
}
ALLOWED_DATETIME = {"date", "time", "datetime", "timedelta", "tzinfo"}
ALLOWED_DT_UTIL = {
    "utcnow",
    "now",
    "as_utc",
    "as_timestamp",
    "as_local",
    "utc_from_timestamp",
    "start_of_local_day",
    "parse_datetime",
    "parse_date",
    "get_age",
}

CONF_FIELDS = "fields"


class ScriptError(HomeAssistantError):
    """When a script error occurs."""


def setup(hass, config):
    """Initialize the Python script component."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning("Folder %s not found in configuration folder", FOLDER)
        return False

    discover_scripts(hass)

    def reload_scripts_handler(call):
        """Handle reload service calls."""
        discover_scripts(hass)

    hass.services.register(DOMAIN, SERVICE_RELOAD, reload_scripts_handler)

    return True


def discover_scripts(hass):
    """Discover python scripts in folder."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning("Folder %s not found in configuration folder", FOLDER)
        return False

    def python_script_service_handler(call):
        """Handle python script service calls."""
        execute_script(hass, call.service, call.data)

    existing = hass.services.services.get(DOMAIN, {}).keys()
    for existing_service in existing:
        if existing_service == SERVICE_RELOAD:
            continue
        hass.services.remove(DOMAIN, existing_service)

    # Load user-provided service descriptions from python_scripts/services.yaml
    services_yaml = os.path.join(path, "services.yaml")
    if os.path.exists(services_yaml):
        services_dict = load_yaml(services_yaml)
    else:
        services_dict = {}

    for fil in glob.iglob(os.path.join(path, "*.py")):
        name = os.path.splitext(os.path.basename(fil))[0]
        hass.services.register(DOMAIN, name, python_script_service_handler)

        service_desc = {
            CONF_NAME: services_dict.get(name, {}).get("name", name),
            CONF_DESCRIPTION: services_dict.get(name, {}).get("description", ""),
            CONF_FIELDS: services_dict.get(name, {}).get("fields", {}),
        }
        async_set_service_schema(hass, DOMAIN, name, service_desc)


@bind_hass
def execute_script(hass, name, data=None):
    """Execute a script."""
    filename = f"{name}.py"
    raise_if_invalid_filename(filename)
    with open(hass.config.path(FOLDER, filename), encoding="utf8") as fil:
        source = fil.read()
    execute(hass, filename, source, data)


@bind_hass
def execute(hass, filename, source, data=None):
    """Execute Python source."""

    compiled = compile_restricted_exec(source, filename=filename)

    if compiled.errors:
        _LOGGER.error(
            "Error loading script %s: %s", filename, ", ".join(compiled.errors)
        )
        return

    if compiled.warnings:
        _LOGGER.warning(
            "Warning loading script %s: %s", filename, ", ".join(compiled.warnings)
        )

    def protected_getattr(obj, name, default=None):
        """Restricted method to get attributes."""
        if name.startswith("async_"):
            raise ScriptError("Not allowed to access async methods")
        if (
            obj is hass
            and name not in ALLOWED_HASS
            or obj is hass.bus
            and name not in ALLOWED_EVENTBUS
            or obj is hass.states
            and name not in ALLOWED_STATEMACHINE
            or obj is hass.services
            and name not in ALLOWED_SERVICEREGISTRY
            or obj is dt_util
            and name not in ALLOWED_DT_UTIL
            or obj is datetime
            and name not in ALLOWED_DATETIME
            or isinstance(obj, TimeWrapper)
            and name not in ALLOWED_TIME
        ):
            raise ScriptError(f"Not allowed to access {obj.__class__.__name__}.{name}")

        return getattr(obj, name, default)

    extra_builtins = {
        "datetime": datetime,
        "sorted": sorted,
        "time": TimeWrapper(),
        "dt_util": dt_util,
        "min": min,
        "max": max,
        "sum": sum,
        "any": any,
        "all": all,
    }
    builtins = safe_builtins.copy()
    builtins.update(utility_builtins)
    builtins.update(limited_builtins)
    builtins.update(extra_builtins)
    logger = logging.getLogger(f"{__name__}.{filename}")
    restricted_globals = {
        "__builtins__": builtins,
        "_print_": StubPrinter,
        "_getattr_": protected_getattr,
        "_write_": full_write_guard,
        "_getiter_": iter,
        "_getitem_": default_guarded_getitem,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_unpack_sequence_": guarded_unpack_sequence,
        "hass": hass,
        "data": data or {},
        "logger": logger,
    }

    try:
        _LOGGER.info("Executing %s: %s", filename, data)
        # pylint: disable=exec-used
        exec(compiled.code, restricted_globals)
    except ScriptError as err:
        logger.error("Error executing script: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Error executing script: %s", err)


class StubPrinter:
    """Class to handle printing inside scripts."""

    def __init__(self, _getattr_):
        """Initialize our printer."""

    def _call_print(self, *objects, **kwargs):
        """Print text."""
        # pylint: disable=no-self-use
        _LOGGER.warning("Don't use print() inside scripts. Use logger.info() instead")


class TimeWrapper:
    """Wrap the time module."""

    # Class variable, only going to warn once per Home Assistant run
    warned = False

    # pylint: disable=no-self-use
    def sleep(self, *args, **kwargs):
        """Sleep method that warns once."""
        if not TimeWrapper.warned:
            TimeWrapper.warned = True
            _LOGGER.warning(
                "Using time.sleep can reduce the performance of Home Assistant"
            )

        time.sleep(*args, **kwargs)

    def __getattr__(self, attr):
        """Fetch an attribute from Time module."""
        attribute = getattr(time, attr)
        if callable(attribute):

            def wrapper(*args, **kw):
                """Wrap to return callable method if callable."""
                return attribute(*args, **kw)

            return wrapper
        return attribute
