"""Script to check the configuration file."""

import argparse
import logging
import os
from collections import OrderedDict, namedtuple
from glob import glob
from platform import system
from unittest.mock import patch

import attr
from typing import Dict, List, Sequence
import voluptuous as vol

from homeassistant import bootstrap, core, loader
from homeassistant.config import (
    get_default_config_dir, CONF_CORE, CORE_CONFIG_SCHEMA,
    CONF_PACKAGES, merge_packages_config, _format_config_error,
    find_config_file, load_yaml_config_file,
    extract_domain_configs, config_per_platform)
import homeassistant.util.yaml as yaml
from homeassistant.exceptions import HomeAssistantError

REQUIREMENTS = ('colorlog==3.1.4',)
if system() == 'Windows':  # Ensure colorama installed for colorlog on Windows
    REQUIREMENTS += ('colorama<=1',)

_LOGGER = logging.getLogger(__name__)
# pylint: disable=protected-access
MOCKS = {
    'load': ("homeassistant.util.yaml.load_yaml", yaml.load_yaml),
    'load*': ("homeassistant.config.load_yaml", yaml.load_yaml),
    'secrets': ("homeassistant.util.yaml._secret_yaml", yaml._secret_yaml),
}
SILENCE = (
    'homeassistant.scripts.check_config.yaml.clear_secret_cache',
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
        description="Check Home Assistant configuration.")
    parser.add_argument(
        '--script', choices=['check_config'])
    parser.add_argument(
        '-c', '--config',
        default=get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '-i', '--info', nargs='?',
        default=None, const='all',
        help="Show a portion of the config")
    parser.add_argument(
        '-f', '--files',
        action='store_true',
        help="Show used configuration files")
    parser.add_argument(
        '-s', '--secrets',
        action='store_true',
        help="Show secret information")

    args, unknown = parser.parse_known_args()
    if unknown:
        print(color('red', "Unknown arguments:", ', '.join(unknown)))

    config_dir = os.path.join(os.getcwd(), args.config)

    print(color('bold', "Testing configuration at", config_dir))

    res = check(config_dir, args.secrets)

    domain_info = []
    if args.info:
        domain_info = args.info.split(',')

    if args.files:
        print(color(C_HEAD, 'yaml files'), '(used /',
              color('red', 'not used') + ')')
        deps = os.path.join(config_dir, 'deps')
        yaml_files = [f for f in glob(os.path.join(config_dir, '**/*.yaml'),
                                      recursive=True)
                      if not f.startswith(deps)]

        for yfn in sorted(yaml_files):
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
            for skey in sdict:
                if skey in flatsecret:
                    _LOGGER.error('Duplicated secrets in files %s and %s',
                                  flatsecret[skey], sfn)
                flatsecret[skey] = sfn
                sss.append(color('green', skey) if skey in res['secrets']
                           else skey)
            print(color(C_HEAD, 'Secrets from', sfn + ':'), ', '.join(sss))

        print(color(C_HEAD, 'Used Secrets:'))
        for skey, sval in res['secrets'].items():
            if sval is None:
                print(' -', skey + ':', color('red', "not found"))
                continue
            print(' -', skey + ':', sval, color('cyan', '[from:', flatsecret
                                                .get(skey, 'keyring') + ']'))

    return len(res['except'])


def check(config_dir, secrets=False):
    """Perform a check by mocking hass load functions."""
    logging.getLogger('homeassistant.loader').setLevel(logging.CRITICAL)
    res = {
        'yaml_files': OrderedDict(),  # yaml_files loaded
        'secrets': OrderedDict(),  # secret cache and secrets loaded
        'except': OrderedDict(),  # exceptions raised (with config)
        'components': None,  # successful components
        'secret_cache': None,
    }

    # pylint: disable=unused-variable
    def mock_load(filename):
        """Mock hass.util.load_yaml to save config file names."""
        res['yaml_files'][filename] = True
        return MOCKS['load'][1](filename)

    # pylint: disable=unused-variable
    def mock_secrets(ldr, node):
        """Mock _get_secrets."""
        try:
            val = MOCKS['secrets'][1](ldr, node)
        except HomeAssistantError:
            val = None
        res['secrets'][node.value] = val
        return val

    # Patches to skip functions
    for sil in SILENCE:
        PATCHES[sil] = patch(sil)

    # Patches with local mock functions
    for key, val in MOCKS.items():
        if not secrets and key == 'secrets':
            continue
        # The * in the key is removed to find the mock_function (side_effect)
        # This allows us to use one side_effect to patch multiple locations
        mock_function = locals()['mock_' + key.replace('*', '')]
        PATCHES[key] = patch(val[0], side_effect=mock_function)

    # Start all patches
    for pat in PATCHES.values():
        pat.start()

    if secrets:
        # Ensure !secrets point to the patched function
        yaml.yaml.SafeLoader.add_constructor('!secret', yaml._secret_yaml)

    try:
        hass = core.HomeAssistant()
        hass.config.config_dir = config_dir

        res['components'] = check_ha_config_file(hass)
        res['secret_cache'] = OrderedDict(yaml.__SECRET_CACHE)

        for err in res['components'].errors:
            domain = err.domain or ERROR_STR
            res['except'].setdefault(domain, []).append(err.message)
            if err.config:
                res['except'].setdefault(domain, []).append(err.config)

    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("BURB")
        print(color('red', 'Fatal error while loading config:'), str(err))
        res['except'].setdefault(ERROR_STR, []).append(str(err))
    finally:
        # Stop all patches
        for pat in PATCHES.values():
            pat.stop()
        if secrets:
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
        key = str(val[0]).lower()
        return '0' if key == 'platform' else key

    indent_str = indent_count * ' '
    if listi or isinstance(layer, list):
        indent_str = indent_str[:-1] + '-'
    if isinstance(layer, Dict):
        for key, value in sorted(layer.items(), key=sort_dict_key):
            if isinstance(value, (dict, list)):
                print(indent_str, str(key) + ':', line_info(value, **kwargs))
                dump_dict(value, indent_count + 2)
            else:
                print(indent_str, str(key) + ':', value)
            indent_str = indent_count * ' '
    if isinstance(layer, Sequence):
        for i in layer:
            if isinstance(i, dict):
                dump_dict(i, indent_count + 2, True)
            else:
                print(' ', indent_str, i)


CheckConfigError = namedtuple(  # pylint: disable=invalid-name
    'CheckConfigError', "message domain config")


@attr.s
class HomeAssistantConfig(OrderedDict):
    """Configuration result with errors attribute."""

    errors = attr.ib(default=attr.Factory(list))

    def add_error(self, message, domain=None, config=None):
        """Add a single error."""
        self.errors.append(CheckConfigError(str(message), domain, config))
        return self


def check_ha_config_file(hass):
    """Check if Home Assistant configuration file is valid."""
    config_dir = hass.config.config_dir
    result = HomeAssistantConfig()

    def _pack_error(package, component, config, message):
        """Handle errors from packages: _log_pkg_error."""
        message = "Package {} setup failed. Component {} {}".format(
            package, component, message)
        domain = 'homeassistant.packages.{}.{}'.format(package, component)
        pack_config = core_config[CONF_PACKAGES].get(package, config)
        result.add_error(message, domain, pack_config)

    def _comp_error(ex, domain, config):
        """Handle errors from components: async_log_exception."""
        result.add_error(
            _format_config_error(ex, domain, config), domain, config)

    # Load configuration.yaml
    try:
        config_path = find_config_file(config_dir)
        if not config_path:
            return result.add_error("File configuration.yaml not found.")
        config = load_yaml_config_file(config_path)
    except HomeAssistantError as err:
        return result.add_error(
            "Error loading {}: {}".format(config_path, err))
    finally:
        yaml.clear_secret_cache()

    # Extract and validate core [homeassistant] config
    try:
        core_config = config.pop(CONF_CORE, {})
        core_config = CORE_CONFIG_SCHEMA(core_config)
        result[CONF_CORE] = core_config
    except vol.Invalid as err:
        result.add_error(err, CONF_CORE, core_config)
        core_config = {}

    # Merge packages
    merge_packages_config(
        hass, config, core_config.get(CONF_PACKAGES, {}), _pack_error)
    del core_config[CONF_PACKAGES]

    # Ensure we have no None values after merge
    for key, value in config.items():
        if not value:
            config[key] = {}

    # Filter out repeating config sections
    components = set(key.split(' ')[0] for key in config.keys())

    # Process and validate config
    for domain in components:
        component = loader.get_component(hass, domain)
        if not component:
            result.add_error("Component not found: {}".format(domain))
            continue

        if hasattr(component, 'CONFIG_SCHEMA'):
            try:
                config = component.CONFIG_SCHEMA(config)
                result[domain] = config[domain]
            except vol.Invalid as ex:
                _comp_error(ex, domain, config)
                continue

        if not hasattr(component, 'PLATFORM_SCHEMA'):
            continue

        platforms = []
        for p_name, p_config in config_per_platform(config, domain):
            # Validate component specific platform schema
            try:
                p_validated = component.PLATFORM_SCHEMA(p_config)
            except vol.Invalid as ex:
                _comp_error(ex, domain, config)
                continue

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            platform = loader.get_platform(hass, domain, p_name)

            if platform is None:
                result.add_error(
                    "Platform not found: {}.{}".format(domain, p_name))
                continue

            # Validate platform specific schema
            if hasattr(platform, 'PLATFORM_SCHEMA'):
                # pylint: disable=no-member
                try:
                    p_validated = platform.PLATFORM_SCHEMA(p_validated)
                except vol.Invalid as ex:
                    _comp_error(
                        ex, '{}.{}'.format(domain, p_name), p_validated)
                    continue

            platforms.append(p_validated)

        # Remove config for current component and add validated config back in.
        for filter_comp in extract_domain_configs(config, domain):
            del config[filter_comp]
        result[domain] = platforms

    return result
