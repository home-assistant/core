"""Component to allow running Python scripts."""
import glob
import os
import logging

import voluptuous as vol

DOMAIN = 'python_script'
REQUIREMENTS = ['restrictedpython==4.0a2']
FOLDER = 'python_scripts'
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema(dict)
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Initialize the python_script component."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning('Folder %s not found in config folder', FOLDER)
        return False

    def service_handler(call):
        """Handle python script service calls."""
        filename = '{}.py'.format(call.service)
        with open(hass.config.path(FOLDER, filename)) as fil:
            execute(hass, filename, fil.read(), call.data)

    for fil in glob.iglob(os.path.join(path, '*.py')):
        name = os.path.splitext(os.path.basename(fil))[0]
        hass.services.register(DOMAIN, name, service_handler)

    return True


def execute(hass, filename, source, data):
    """Execute a script."""
    from RestrictedPython import compile_restricted_exec
    from RestrictedPython.Guards import safe_builtins, full_write_guard

    compiled = compile_restricted_exec(source, filename=filename)

    if compiled.errors:
        _LOGGER.error('Error loading script %s: %s', filename,
                      ', '.join(compiled.errors))
        return

    if compiled.warnings:
        _LOGGER.warning('Warning loading script %s: %s', filename,
                        ', '.join(compiled.warnings))

    restricted_globals = {
        '__builtins__': safe_builtins,
        '_print_': StubPrinter,
        '_getattr_': getattr,
        '_write_': full_write_guard,
    }
    local = {
        'hass': hass,
        'data': data,
        'logger': logging.getLogger('{}.{}'.format(__name__, filename))
    }

    try:
        _LOGGER.info('Executing %s: %s', filename, data)
        # pylint: disable=exec-used
        exec(compiled.code, restricted_globals, local)
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception('Error executing script %s: %s', filename, err)


class StubPrinter:
    """Class to handle printing inside scripts."""

    def __init__(self, _getattr_):
        """Initialize our printer."""
        pass

    def _call_print(self, *objects, **kwargs):
        """Print text."""
        # pylint: disable=no-self-use
        _LOGGER.warning(
            "Don't use print() inside scripts. Use logger.info() instead.")
