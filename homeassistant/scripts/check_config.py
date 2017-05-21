"""Script to ensure a configuration file exists."""
import argparse
import logging
import os
from collections import OrderedDict
from glob import glob
from platform import system
from unittest.mock import patch

from typing import Dict, List, Sequence

from homeassistant import bootstrap, loader, setup, config as config_util
import homeassistant.util.yaml as yaml
from homeassistant.exceptions import HomeAssistantError

REQUIREMENTS = ('colorlog>2.1,<3',)
if system() == 'Windows':  # Ensure colorama installed for colorlog on Windows
    REQUIREMENTS += ('colorama<=1',)

_LOGGER = logging.getLogger(__name__)
# pylint: disable=protected-access
MOCKS = {
    'load': ("homeassistant.util.yaml.load_yaml", yaml.load_yaml),
    'load*': ("homeassistant.config.load_yaml", yaml.load_yaml),
    'get': ("homeassistant.loader.get_component", loader.get_component),
    'secrets': ("homeassistant.util.yaml._secret_yaml", yaml._secret_yaml),
    'except': ("homeassistant.config.async_log_exception",
               config_util.async_log_exception),
    'package_error': ("homeassistant.config._log_pkg_error",
                      config_util._log_pkg_error),
    'logger_exception': ("homeassistant.setup._LOGGER.error",
                         setup._LOGGER.error),
}
SILENCE = (
    'homeassistant.bootstrap.clear_secret_cache',
    'homeassistant.bootstrap.async_register_signal_handling',
    'homeassistant.core._LOGGER.info',
    'homeassistant.loader._LOGGER.info',
    'homeassistant.bootstrap._LOGGER.info',
    'homeassistant.bootstrap._LOGGER.warning',
    'homeassistant.util.yaml._LOGGER.debug',
)
PATCHES = {}

C_HEAD = 'bold'
ERROR_STR = 'General Errors'


def color(the_color, *args, reset=None):
    """Color helper."""
    from colorlog.escape_codes import escape_codes, parse_colors
    try:
        if not args:
            assert reset is None, "You cannot reset if nothing being printed"
            return parse_colors(the_color)
        return parse_colors(the_color) + ' '.join(args) + \
            escape_codes[reset or 'reset']
    except KeyError as k:
        raise ValueError("Invalid color {} in {}".format(str(k), the_color))


def run(script_args: List) -> int:
    """Handle ensure config commandline script."""
    parser = argparse.ArgumentParser(
        description=("Check Home Assistant configuration."))
    parser.add_argument(
        '--script', choices=['check_config'])
    parser.add_argument(
        '-c', '--config',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '-i', '--info',
        default=None,
        help="Show a portion of the config")
    parser.add_argument(
        '-f', '--files',
        action='store_true',
        help="Show used configuration files")
    parser.add_argument(
        '-s', '--secrets',
        action='store_true',
        help="Show secret information")

    args = parser.parse_args()

    config_dir = os.path.join(os.getcwd(), args.config)
    config_path = os.path.join(config_dir, 'configuration.yaml')
    if not os.path.isfile(config_path):
        print('Config does not exist:', config_path)
        return 1

    print(color('bold', "Testing configuration at", config_dir))

    domain_info = []
    if args.info:
        domain_info = args.info.split(',')

    res = check(config_path)
    if args.files:
        print(color(C_HEAD, 'yaml files'), '(used /',
              color('red', 'not used') + ')')
        # Python 3.5 gets a recursive, but not in 3.4
        for yfn in sorted(glob(os.path.join(config_dir, '*.yaml')) +
                          glob(os.path.join(config_dir, '*/*.yaml'))):
            the_color = '' if yfn in res['yaml_files'] else 'red'
            print(color(the_color, '-', yfn))

    if res['except']:
        print(color('bold_white', 'Failed config'))
        for domain, config in res['except'].items():
            domain_info.append(domain)
            print(' ', color('bold_red', domain + ':'),
                  color('red', '', reset='red'))
            dump_dict(config, reset='red')
            print(color('reset'))

    if domain_info:
        if 'all' in domain_info:
            print(color('bold_white', 'Successful config (all)'))
            for domain, config in res['components'].items():
                print(' ', color(C_HEAD, domain + ':'))
                dump_dict(config)
        else:
            print(color('bold_white', 'Successful config (partial)'))
            for domain in domain_info:
                if domain == ERROR_STR:
                    continue
                print(' ', color(C_HEAD, domain + ':'))
                dump_dict(res['components'].get(domain, None))

    if args.secrets:
        flatsecret = {}

        for sfn, sdict in res['secret_cache'].items():
            sss = []
            for skey, sval in sdict.items():
                if skey in flatsecret:
                    _LOGGER.error('Duplicated secrets in files %s and %s',
                                  flatsecret[skey], sfn)
                flatsecret[skey] = sfn
                sss.append(color('green', skey) if skey in res['secrets']
                           else skey)
            print(color(C_HEAD, 'Secrets from', sfn + ':'), ', '.join(sss))

        print(color(C_HEAD, 'Used Secrets:'))
        for skey, sval in res['secrets'].items():
            print(' -', skey + ':', sval, color('cyan', '[from:', flatsecret
                                                .get(skey, 'keyring') + ']'))

    return len(res['except'])


def check(config_path):
    """Perform a check by mocking hass load functions."""
    res = {
        'yaml_files': OrderedDict(),  # yaml_files loaded
        'secrets': OrderedDict(),  # secret cache and secrets loaded
        'except': OrderedDict(),  # exceptions raised (with config)
        'components': OrderedDict(),  # successful components
        'secret_cache': OrderedDict(),
    }

    # pylint: disable=unused-variable
    def mock_load(filename):
        """Mock hass.util.load_yaml to save config files."""
        res['yaml_files'][filename] = True
        return MOCKS['load'][1](filename)

    # pylint: disable=unused-variable
    def mock_get(comp_name):
        """Mock hass.loader.get_component to replace setup & setup_platform."""
        def mock_setup(*kwargs):
            """Mock setup, only record the component name & config."""
            assert comp_name not in res['components'], \
                "Components should contain a list of platforms"
            res['components'][comp_name] = kwargs[1].get(comp_name)
            return True
        module = MOCKS['get'][1](comp_name)

        if module is None:
            # Ensure list
            msg = '{} not found: {}'.format(
                'Platform' if '.' in comp_name else 'Component', comp_name)
            res['except'].setdefault(ERROR_STR, []).append(msg)
            return None

        # Test if platform/component and overwrite setup
        if '.' in comp_name:
            module.setup_platform = mock_setup

            if hasattr(module, 'async_setup_platform'):
                del module.async_setup_platform
        else:
            module.setup = mock_setup

            if hasattr(module, 'async_setup'):
                del module.async_setup

        return module

    # pylint: disable=unused-variable
    def mock_secrets(ldr, node):
        """Mock _get_secrets."""
        try:
            val = MOCKS['secrets'][1](ldr, node)
        except HomeAssistantError:
            val = None
        res['secrets'][node.value] = val
        return val

    def mock_except(ex, domain, config,  # pylint: disable=unused-variable
                    hass=None):
        """Mock config.log_exception."""
        MOCKS['except'][1](ex, domain, config, hass)
        res['except'][domain] = config.get(domain, config)

    def mock_package_error(  # pylint: disable=unused-variable
            package, component, config, message):
        """Mock config_util._log_pkg_error."""
        MOCKS['package_error'][1](package, component, config, message)

        pkg_key = 'homeassistant.packages.{}'.format(package)
        res['except'][pkg_key] = config.get('homeassistant', {}) \
            .get('packages', {}).get(package)

    def mock_logger_exception(msg, *params):
        """Log logger.exceptions."""
        res['except'].setdefault(ERROR_STR, []).append(msg % params)
        MOCKS['logger_exception'][1](msg, *params)

    # Patches to skip functions
    for sil in SILENCE:
        PATCHES[sil] = patch(sil)

    # Patches with local mock functions
    for key, val in MOCKS.items():
        # The * in the key is removed to find the mock_function (side_effect)
        # This allows us to use one side_effect to patch multiple locations
        mock_function = locals()['mock_' + key.replace('*', '')]
        PATCHES[key] = patch(val[0], side_effect=mock_function)

    # Start all patches
    for pat in PATCHES.values():
        pat.start()
    # Ensure !secrets point to the patched function
    yaml.yaml.SafeLoader.add_constructor('!secret', yaml._secret_yaml)

    try:
        with patch('homeassistant.util.logging.AsyncHandler._process'):
            bootstrap.from_config_file(config_path, skip_pip=True)
        res['secret_cache'] = dict(yaml.__SECRET_CACHE)
    except Exception as err:  # pylint: disable=broad-except
        print(color('red', 'Fatal error while loading config:'), str(err))
        res['except'].setdefault(ERROR_STR, []).append(err)
    finally:
        # Stop all patches
        for pat in PATCHES.values():
            pat.stop()
        # Ensure !secrets point to the original function
        yaml.yaml.SafeLoader.add_constructor('!secret', yaml._secret_yaml)
        bootstrap.clear_secret_cache()

    return res


def line_info(obj, **kwargs):
    """Display line config source."""
    if hasattr(obj, '__config_file__'):
        return color('cyan', "[source {}:{}]"
                     .format(obj.__config_file__, obj.__line__ or '?'),
                     **kwargs)
    return '?'


def dump_dict(layer, indent_count=3, listi=False, **kwargs):
    """Display a dict.

    A friendly version of print yaml.yaml.dump(config).
    """
    def sort_dict_key(val):
        """Return the dict key for sorting."""
        key = str.lower(val[0])
        return '0' if key == 'platform' else key

    indent_str = indent_count * ' '
    if listi or isinstance(layer, list):
        indent_str = indent_str[:-1] + '-'
    if isinstance(layer, Dict):
        for key, value in sorted(layer.items(), key=sort_dict_key):
            if isinstance(value, dict) or isinstance(value, list):
                print(indent_str, key + ':', line_info(value, **kwargs))
                dump_dict(value, indent_count + 2)
            else:
                print(indent_str, key + ':', value)
            indent_str = indent_count * ' '
    if isinstance(layer, Sequence):
        for i in layer:
            if isinstance(i, dict):
                dump_dict(i, indent_count + 2, True)
            else:
                print(' ', indent_str, i)
