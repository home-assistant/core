"""Component to allow running Python scripts."""
import glob
import os
import logging

DOMAIN = 'python_script'
REQUIREMENTS = ['restrictedpython==4.0a2']
FOLDER = 'python_scripts'
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Initialize the python_script component."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning('Folder %s not found in config folder', FOLDER)
        return False

    def service_handler(call):
        """Handle python script service calls."""
        execute(hass, call.service, call.data)

    for fil in glob.iglob(os.path.join(path, '*.py')):
        name = os.path.splitext(os.path.basename(fil))[0]
        hass.services.register(DOMAIN, name, service_handler)

    return True


def execute(hass, name, data):
    """Execute a script."""
    from RestrictedPython import compile_restricted_exec
    from RestrictedPython.Guards import safe_builtins, full_write_guard

    filename = '{}.py'.format(name)
    with open(hass.config.path(FOLDER, filename)) as fil:
        compiled = compile_restricted_exec(fil.read(), filename=filename)

    if compiled.errors:
        _LOGGER.error('Error loading script: %s',
                      ', '.join(compiled.errors))
        return

    if compiled.warnings:
        _LOGGER.warning('Warning loading script: %s',
                        ', '.join(compiled.warnings))

    restricted_globals = {
        '__builtins__': safe_builtins,
        '_print_': Printer,
        '_getattr_': getattr,
        '_write_': full_write_guard,
    }
    local = {
        'hass': hass,
        'data': data,
    }

    try:
        _LOGGER.info('Executing %s: %s', name, data)
        # pylint: disable=exec-used
        exec(compiled.code, restricted_globals, local)
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception('Error executing script: %s', err)


class Printer:
    """Class to handle printing inside scripts."""

    def __init__(self, _getattr_):
        """Initialize our printer."""
        pass

    def _call_print(self, *objects, **kwargs):
        """Print text."""
        # pylint: disable=no-self-use
        print(*objects, **kwargs)
